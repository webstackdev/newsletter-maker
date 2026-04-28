import json
from base64 import b64encode
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import Group
from django.core import mail
from django.urls import reverse
from svix.webhooks import Webhook

from core.models import Content, IntakeAllowlist, NewsletterIntake, NewsletterIntakeStatus, Project
from core.newsletters import (
    extract_newsletter_items,
    sanitize_newsletter_html,
    send_confirmation_email,
)
from core.signals import handle_anymail_inbound

pytestmark = pytest.mark.django_db


@pytest.fixture
def project():
    group = Group.objects.create(name="newsletter-team")
    return Project.objects.create(
        name="Newsletter Project",
        group=group,
        topic_description="Platform engineering",
        intake_enabled=True,
    )


def test_sanitize_newsletter_html_removes_scripts_and_inline_handlers():
    sanitized = sanitize_newsletter_html('<div onclick="alert(1)"><script>alert(2)</script><a href="https://example.com">Read</a></div>')

    assert "<script" not in sanitized
    assert "onclick=" not in sanitized


def test_extract_newsletter_items_prefers_anchor_titles_and_dedupes_urls():
    items = extract_newsletter_items(
        subject="Weekly Digest",
        raw_html='<a href="https://example.com/a">Article A</a><a href="https://example.com/a">Duplicate</a>',
        raw_text='See also https://example.com/b and https://example.com/a',
    )

    assert [item.url for item in items] == ["https://example.com/a", "https://example.com/b"]
    assert items[0].title == "Article A"
    assert items[1].title == "Weekly Digest"


class FakeInboundMessage:
    def __init__(
        self,
        *,
        envelope_recipient: str | None,
        from_email: str,
        subject: str,
        html: str,
        text: str,
        message_id: str,
        to: list[str] | None = None,
    ) -> None:
        self.envelope_recipient = envelope_recipient
        self.envelope_sender = from_email
        self.from_email = SimpleNamespace(addr_spec=from_email)
        self.subject = subject
        self.html = html
        self.text = text
        self.to = [SimpleNamespace(addr_spec=address) for address in (to or [])]
        self._headers = {"Message-ID": message_id}

    def get(self, key: str, default=None):
        return self._headers.get(key, default)


def _signed_resend_headers(secret: str, payload: str, *, message_id: str) -> dict[str, str]:
    timestamp = datetime.now(timezone.utc)
    signature = Webhook(secret).sign(
        msg_id=message_id,
        timestamp=timestamp,
        data=payload,
    )
    return {
        "HTTP_SVIX_ID": message_id,
        "HTTP_SVIX_TIMESTAMP": str(int(timestamp.timestamp())),
        "HTTP_SVIX_SIGNATURE": signature,
    }


def _basic_auth_header(credentials: str) -> str:
    encoded = b64encode(credentials.encode("utf-8")).decode("ascii")
    return f"Basic {encoded}"


def test_handle_anymail_inbound_creates_pending_intake_and_sends_confirmation(settings, mocker, project):
    settings.NEWSLETTER_API_BASE_URL = "https://example.com"
    send_mock = mocker.patch("core.newsletters.send_confirmation_email")
    event = SimpleNamespace(
        message=FakeInboundMessage(
            envelope_recipient=f"intake+{project.intake_token}@inbox.example.com",
            from_email="newsletter@example.com",
            subject="Weekly Digest",
            html='<a href="https://example.com/post">Read now</a>',
            text="Read https://example.com/post",
            message_id="msg-123",
        ),
        event_id=None,
    )

    handle_anymail_inbound(sender=object(), event=event, esp_name="Resend")

    intake = NewsletterIntake.objects.get(message_id="msg-123")
    allowlist = IntakeAllowlist.objects.get(project=project, sender_email="newsletter@example.com")
    assert intake.status == NewsletterIntakeStatus.PENDING
    assert allowlist.confirmed_at is None
    send_mock.assert_called_once()
    assert send_mock.call_args.kwargs["confirm_url"].startswith("https://example.com/api/v1/inbound/confirm/")


def test_handle_anymail_inbound_queues_confirmed_sender(settings, mocker, project):
    settings.CELERY_TASK_ALWAYS_EAGER = False
    send_mock = mocker.patch("core.newsletters.send_confirmation_email")
    delay_mock = mocker.patch("core.tasks.process_newsletter_intake.delay")
    IntakeAllowlist.objects.create(
        project=project,
        sender_email="newsletter@example.com",
        confirmed_at="2026-04-28T00:00:00Z",
    )
    event = SimpleNamespace(
        message=FakeInboundMessage(
            envelope_recipient=f"intake+{project.intake_token}@inbox.example.com",
            from_email="newsletter@example.com",
            subject="Weekly Digest",
            html='<a href="https://example.com/post">Read now</a>',
            text="Read https://example.com/post",
            message_id="msg-456",
        ),
        event_id=None,
    )

    handle_anymail_inbound(sender=object(), event=event, esp_name="Resend")

    intake = NewsletterIntake.objects.get(message_id="msg-456")
    delay_mock.assert_called_once_with(intake.id)
    send_mock.assert_not_called()


def test_resend_inbound_webhook_posts_to_anymail_url(settings, client, mocker, project):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.DEFAULT_FROM_EMAIL = "noreply@example.com"
    settings.NEWSLETTER_API_BASE_URL = "https://example.com"
    settings.RESEND_API_KEY = "re_test_key"
    settings.RESEND_INBOUND_SECRET = "whsec_test_secret"
    settings.ANYMAIL = {
        "RESEND_API_KEY": settings.RESEND_API_KEY,
        "RESEND_INBOUND_SECRET": settings.RESEND_INBOUND_SECRET,
    }

    api_response = mocker.Mock()
    api_response.raise_for_status.return_value = None
    api_response.json.return_value = {
        "from": "newsletter@example.com",
        "to": [f"intake+{project.intake_token}@inbox.example.com"],
        "subject": "Weekly Digest",
        "text": "Read https://example.com/post",
        "html": '<a href="https://example.com/post">Read now</a>',
        "message_id": "<msg-789@example.com>",
        "headers": {
            "Message-ID": "<msg-789@example.com>",
        },
        "attachments": [],
    }
    mocker.patch("anymail.webhooks.resend.requests.get", return_value=api_response)

    payload = json.dumps(
        {
            "type": "email.received",
            "created_at": "2026-04-28T12:00:00.000Z",
            "data": {
                "email_id": "re_email_123",
            },
        }
    )

    response = client.post(
        "/anymail/resend/inbound/",
        data=payload,
        content_type="application/json",
        **_signed_resend_headers(
            settings.RESEND_INBOUND_SECRET,
            payload,
            message_id="msg_resend_123",
        ),
    )

    assert response.status_code == 200
    intake = NewsletterIntake.objects.get(message_id="<msg-789@example.com>")
    allowlist = IntakeAllowlist.objects.get(project=project, sender_email="newsletter@example.com")
    assert intake.status == NewsletterIntakeStatus.PENDING
    assert allowlist.confirmed_at is None
    assert len(mail.outbox) == 1
    assert "/api/v1/inbound/confirm/" in mail.outbox[0].body


def test_amazon_ses_inbound_webhook_posts_to_anymail_url(settings, client, project):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.DEFAULT_FROM_EMAIL = "noreply@example.com"
    settings.NEWSLETTER_API_BASE_URL = "https://example.com"
    settings.ANYMAIL = {
        "WEBHOOK_SECRET": "anymail:ses-secret",
    }

    payload = json.dumps(
        {
            "Type": "Notification",
            "MessageId": "sns-message-123",
            "TopicArn": "arn:aws:sns:us-east-1:123456789012:ses-inbound",
            "Message": json.dumps(
                {
                    "notificationType": "Received",
                    "mail": {
                        "messageId": "ses-message-123",
                        "timestamp": "2026-04-28T12:00:00.000Z",
                        "source": "newsletter@example.com",
                    },
                    "receipt": {
                        "action": {
                            "type": "SNS",
                            "encoding": "UTF-8",
                        },
                        "recipients": [
                            f"intake+{project.intake_token}@inbox.example.com",
                        ],
                        "spamVerdict": {
                            "status": "PASS",
                        },
                    },
                    "content": (
                        "From: newsletter@example.com\n"
                        f"To: intake+{project.intake_token}@inbox.example.com\n"
                        "Subject: SES Digest\n"
                        "Message-ID: <ses-message-123@example.com>\n"
                        "Content-Type: text/plain; charset=utf-8\n"
                        "\n"
                        "Read https://example.com/post\n"
                    ),
                }
            ),
        }
    )

    response = client.post(
        "/anymail/amazon_ses/inbound/",
        data=payload,
        content_type="application/json",
        HTTP_X_AMZ_SNS_MESSAGE_TYPE="Notification",
        HTTP_X_AMZ_SNS_MESSAGE_ID="sns-message-123",
        HTTP_AUTHORIZATION=_basic_auth_header(settings.ANYMAIL["WEBHOOK_SECRET"]),
    )

    assert response.status_code == 200
    intake = NewsletterIntake.objects.get(message_id="<ses-message-123@example.com>")
    allowlist = IntakeAllowlist.objects.get(project=project, sender_email="newsletter@example.com")
    assert intake.status == NewsletterIntakeStatus.PENDING
    assert allowlist.confirmed_at is None
    assert len(mail.outbox) == 1
    assert "/api/v1/inbound/confirm/" in mail.outbox[0].body


def test_send_confirmation_email_uses_django_mail_backend(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.DEFAULT_FROM_EMAIL = "noreply@example.com"

    send_confirmation_email(
        to_email="newsletter@example.com",
        confirm_url="https://example.com/confirm/token",
        project_name="Platform Engineering Weekly",
    )

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.subject == "Confirm newsletter intake for Platform Engineering Weekly"
    assert message.from_email == "noreply@example.com"
    assert message.to == ["newsletter@example.com"]
    assert "https://example.com/confirm/token" in message.body
    assert any(
        mimetype == "text/html" and "Confirm sender" in content
        for content, mimetype in message.alternatives
    )


def test_confirm_newsletter_sender_confirms_allowlist_and_queues_pending_intakes(client, settings, mocker, project):
    settings.CELERY_TASK_ALWAYS_EAGER = False
    allowlist = IntakeAllowlist.objects.create(project=project, sender_email="newsletter@example.com")
    intake = NewsletterIntake.objects.create(
        project=project,
        sender_email="newsletter@example.com",
        subject="Digest",
        raw_text="Visit https://example.com/post",
        message_id="msg-456",
    )
    delay_mock = mocker.patch("core.tasks.process_newsletter_intake.delay")

    response = client.get(reverse("confirm-newsletter-sender", kwargs={"token": allowlist.confirmation_token}))

    assert response.status_code == 200
    allowlist.refresh_from_db()
    assert allowlist.confirmed_at is not None
    delay_mock.assert_called_once_with(intake.id)


def test_process_newsletter_intake_creates_content_for_confirmed_sender(settings, mocker, project):
    settings.CELERY_TASK_ALWAYS_EAGER = False
    allowlist = IntakeAllowlist.objects.create(
        project=project,
        sender_email="newsletter@example.com",
        confirmed_at="2026-04-28T00:00:00Z",
    )
    intake = NewsletterIntake.objects.create(
        project=project,
        sender_email=allowlist.sender_email,
        subject="Digest",
        raw_html='<a href="https://example.com/article">Great Article</a>',
        raw_text="Great article https://example.com/article",
        message_id="msg-789",
    )
    upsert_mock = mocker.patch("core.tasks.upsert_content_embedding")
    delay_mock = mocker.patch("core.tasks.process_content.delay")

    from core.tasks import process_newsletter_intake

    result = process_newsletter_intake(intake.id)

    assert result["items_ingested"] == 1
    intake.refresh_from_db()
    content = Content.objects.get(project=project, url="https://example.com/article")
    assert intake.status == NewsletterIntakeStatus.EXTRACTED
    assert intake.extraction_result["method"] == "heuristic"
    assert content.source_plugin == "newsletter"
    assert content.source_metadata["newsletter_intake_id"] == intake.id
    upsert_mock.assert_called_once_with(content)
    delay_mock.assert_called_once_with(content.id)
