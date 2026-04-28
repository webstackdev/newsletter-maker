from __future__ import annotations

import re
from dataclasses import dataclass
from email.utils import parseaddr
from html.parser import HTMLParser
from typing import Any, Iterable, cast

from django.conf import settings as django_settings
from django.core.mail import EmailMultiAlternatives
from django.urls import reverse

from core.models import IntakeAllowlist, NewsletterIntake, Project
from core.settings_types import CoreSettings

settings = cast(CoreSettings, django_settings)

SCRIPT_TAG_PATTERN = re.compile(r"<script\b[^<]*(?:(?!</script>)<[^<]*)*</script>", re.IGNORECASE | re.DOTALL)
INLINE_HANDLER_PATTERN = re.compile(r"\son[a-z]+=(?:\"[^\"]*\"|'[^']*')", re.IGNORECASE)
URL_PATTERN = re.compile(r"https?://[^\s<>'\"]+")


def normalize_sender_email(value: str) -> str:
    _, email_address = parseaddr(value)
    return email_address.strip().lower()


def sanitize_newsletter_html(raw_html: str) -> str:
    without_scripts = SCRIPT_TAG_PATTERN.sub("", raw_html)
    return INLINE_HANDLER_PATTERN.sub("", without_scripts)


def extract_project_token(recipient: str) -> str | None:
    _, email_address = parseaddr(recipient)
    local_part = email_address.partition("@")[0]
    prefix, separator, token = local_part.partition("+")
    if prefix != "intake" or separator != "+" or not token:
        return None
    return token


def send_confirmation_email(*, to_email: str, confirm_url: str, project_name: str) -> None:
    subject = f"Confirm newsletter intake for {project_name}"
    text_body = (
        "Confirm this sender for newsletter ingestion.\n\n"
        f"Confirm sender: {confirm_url}"
    )
    html_body = (
        "<p>Confirm this sender for newsletter ingestion.</p>"
        f'<p><a href="{confirm_url}">Confirm sender</a></p>'
    )

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send()


def build_confirmation_url(token: str) -> str:
    base_url = settings.NEWSLETTER_API_BASE_URL.rstrip("/")
    return f"{base_url}{reverse('confirm-newsletter-sender', kwargs={'token': token})}"


def process_inbound_newsletter(
    *,
    recipients: Iterable[str],
    sender_email: str,
    subject: str,
    raw_html: str,
    raw_text: str,
    message_id: str,
) -> dict[str, Any]:
    project = _find_intake_project(recipients)
    if project is None:
        return {"status": "ignored", "reason": "no_matching_project"}

    normalized_sender_email = normalize_sender_email(sender_email)
    normalized_message_id = message_id.strip()
    if not normalized_sender_email or not normalized_message_id:
        return {"status": "ignored", "reason": "missing_sender_or_message_id"}

    defaults = {
        "project": project,
        "sender_email": normalized_sender_email,
        "subject": subject[:512],
        "raw_html": sanitize_newsletter_html(raw_html),
        "raw_text": raw_text,
    }
    intake, created = NewsletterIntake.objects.get_or_create(
        message_id=normalized_message_id,
        defaults=defaults,
    )
    if not created:
        return {"id": intake.id, "status": intake.status, "duplicate": True}

    allowlist, allowlist_created = IntakeAllowlist.objects.get_or_create(
        project=project,
        sender_email=normalized_sender_email,
    )

    if allowlist.is_confirmed:
        queue_newsletter_intake(intake.id)
        return {"id": intake.id, "status": intake.status}

    if allowlist_created:
        send_confirmation_email(
            to_email=normalized_sender_email,
            confirm_url=build_confirmation_url(allowlist.confirmation_token),
            project_name=project.name,
        )

    return {"id": intake.id, "status": intake.status, "confirmation_required": True}


def queue_newsletter_intake(intake_id: int) -> None:
    from core.tasks import process_newsletter_intake

    if settings.CELERY_TASK_ALWAYS_EAGER:
        process_newsletter_intake(intake_id)
    else:
        process_newsletter_intake.delay(intake_id)


def _find_intake_project(recipients: Iterable[str]) -> Project | None:
    for recipient in recipients:
        token = extract_project_token(recipient)
        if token is None:
            continue
        project = Project.objects.filter(intake_token=token, intake_enabled=True).first()
        if project is not None:
            return project
    return None


@dataclass(slots=True)
class ExtractedNewsletterItem:
    url: str
    title: str
    excerpt: str
    position: int


class _NewsletterLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[dict[str, str]] = []
        self._active_href: str | None = None
        self._active_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value and value.startswith(("http://", "https://")):
                self._active_href = value
                self._active_text = []
                return

    def handle_data(self, data: str) -> None:
        if self._active_href is not None:
            self._active_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._active_href is None:
            return
        self.links.append(
            {
                "url": self._active_href,
                "title": " ".join(part.strip() for part in self._active_text if part.strip()),
            }
        )
        self._active_href = None
        self._active_text = []


def extract_newsletter_items(*, subject: str, raw_html: str, raw_text: str) -> list[ExtractedNewsletterItem]:
    parser = _NewsletterLinkParser()
    if raw_html:
        parser.feed(raw_html)

    seen_urls: set[str] = set()
    extracted_items: list[ExtractedNewsletterItem] = []
    for candidate in parser.links:
        url = candidate["url"].strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        extracted_items.append(
            ExtractedNewsletterItem(
                url=url,
                title=candidate["title"] or subject or url,
                excerpt=raw_text[:500].strip(),
                position=len(extracted_items) + 1,
            )
        )

    for match in URL_PATTERN.finditer(raw_text):
        url = match.group(0).rstrip(".,)")
        if url in seen_urls:
            continue
        seen_urls.add(url)
        extracted_items.append(
            ExtractedNewsletterItem(
                url=url,
                title=subject or url,
                excerpt=raw_text[:500].strip(),
                position=len(extracted_items) + 1,
            )
        )

    return extracted_items
