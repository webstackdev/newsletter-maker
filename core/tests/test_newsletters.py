import json

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from core.models import Content, IntakeAllowlist, NewsletterIntake, NewsletterIntakeStatus, Project
from core.newsletters import compute_resend_signature, extract_newsletter_items, sanitize_newsletter_html


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


def test_resend_inbound_webhook_rejects_invalid_signature(client, settings):
    settings.RESEND_WEBHOOK_SECRET = "secret"

    response = client.post(
        reverse("resend-inbound-webhook"),
        data=json.dumps({"data": {}}),
        content_type="application/json",
        HTTP_X_RESEND_SIGNATURE="wrong",
    )

    assert response.status_code == 401


def test_resend_inbound_webhook_creates_pending_intake_and_sends_confirmation(client, settings, mocker, project):
    settings.RESEND_WEBHOOK_SECRET = "secret"
    settings.RESEND_API_KEY = "resend-key"
    send_mock = mocker.patch("core.views.send_confirmation_email")
    payload = {
        "data": {
            "from": "Sender <newsletter@example.com>",
            "to": [f"intake+{project.intake_token}@inbox.example.com"],
            "subject": "Weekly Digest",
            "html": '<a href="https://example.com/post">Read now</a>',
            "text": "Read https://example.com/post",
            "message_id": "msg-123",
        }
    }
    raw_payload = json.dumps(payload)

    response = client.post(
        reverse("resend-inbound-webhook"),
        data=raw_payload,
        content_type="application/json",
        HTTP_X_RESEND_SIGNATURE=compute_resend_signature(raw_payload.encode("utf-8"), settings.RESEND_WEBHOOK_SECRET),
    )

    assert response.status_code == 202
    intake = NewsletterIntake.objects.get(message_id="msg-123")
    allowlist = IntakeAllowlist.objects.get(project=project, sender_email="newsletter@example.com")
    assert intake.status == NewsletterIntakeStatus.PENDING
    assert allowlist.confirmed_at is None
    send_mock.assert_called_once()


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
    delay_mock = mocker.patch("core.views.process_newsletter_intake.delay")

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