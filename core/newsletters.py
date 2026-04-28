from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from email.utils import parseaddr
from html.parser import HTMLParser
from typing import Any, cast

from django.conf import settings as django_settings

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


def compute_resend_signature(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_resend_signature(payload: bytes, provided_signature: str) -> bool:
    if not settings.RESEND_WEBHOOK_SECRET or not provided_signature:
        return False
    expected_signature = compute_resend_signature(payload, settings.RESEND_WEBHOOK_SECRET)
    return hmac.compare_digest(expected_signature, provided_signature)


def extract_project_token(recipient: str) -> str | None:
    _, email_address = parseaddr(recipient)
    local_part = email_address.partition("@")[0]
    prefix, separator, token = local_part.partition("+")
    if prefix != "intake" or separator != "+" or not token:
        return None
    return token


def send_confirmation_email(*, to_email: str, confirm_url: str, project_name: str) -> None:
    if not settings.RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY must be configured to send newsletter confirmation emails.")

    import resend

    resend.api_key = settings.RESEND_API_KEY
    resend.Emails.send(
        {
            "from": settings.RESEND_FROM_EMAIL,
            "to": [to_email],
            "subject": f"Confirm newsletter intake for {project_name}",
            "html": (
                "<p>Confirm this sender for newsletter ingestion.</p>"
                f'<p><a href="{confirm_url}">Confirm sender</a></p>'
            ),
        }
    )


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


def get_resend_payload_data(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    if isinstance(data, dict):
        return data
    return payload