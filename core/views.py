from http import HTTPStatus
import json
from typing import cast

from django.conf import settings as django_settings
from django.db import connection
from django.http import HttpRequest
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from qdrant_client import QdrantClient

from core.models import IntakeAllowlist, NewsletterIntake, NewsletterIntakeStatus, Project
from core.newsletters import (
    get_resend_payload_data,
    normalize_sender_email,
    sanitize_newsletter_html,
    send_confirmation_email,
    verify_resend_signature,
)
from core.settings_types import CoreSettings
from core.tasks import process_newsletter_intake

settings = cast(CoreSettings, django_settings)


def healthz_view(request):
    return JsonResponse({"status": "ok", "service": "newsletter-maker"}, status=HTTPStatus.OK)


def readyz_view(request):
    checks = {
        "database": _check_database(),
        "qdrant": _check_qdrant(),
    }
    status = HTTPStatus.OK if all(checks.values()) else HTTPStatus.SERVICE_UNAVAILABLE
    payload = {
        "status": "ready" if status == HTTPStatus.OK else "degraded",
        "checks": checks,
    }
    return JsonResponse(payload, status=status)


def _check_database() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return False
    return True


def _check_qdrant() -> bool:
    try:
        client = QdrantClient(url=settings.QDRANT_URL, timeout=2, check_compatibility=False)
        client.get_collections()
    except Exception:
        return False
    return True


@csrf_exempt
@require_POST
def resend_inbound_webhook_view(request: HttpRequest):
    body = request.body
    if len(body) > 1_000_000:
        return JsonResponse({"detail": "Payload too large."}, status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE)

    signature = request.headers.get("X-Resend-Signature", "")
    if not verify_resend_signature(body, signature):
        return JsonResponse({"detail": "Invalid webhook signature."}, status=HTTPStatus.UNAUTHORIZED)

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=HTTPStatus.BAD_REQUEST)

    payload_data = get_resend_payload_data(payload)
    recipients = payload_data.get("to") or []
    if isinstance(recipients, str):
        recipients = [recipients]

    project = None
    for recipient in recipients:
        token = _extract_project_token_from_recipient(recipient)
        if token is None:
            continue
        project = Project.objects.filter(intake_token=token, intake_enabled=True).first()
        if project is not None:
            break

    if project is None:
        return JsonResponse({"detail": "No matching intake project found."}, status=HTTPStatus.NOT_FOUND)

    sender_email = normalize_sender_email(str(payload_data.get("from", "")))
    message_id = str(payload_data.get("message_id") or payload_data.get("email_id") or payload_data.get("id") or "").strip()
    if not sender_email or not message_id:
        return JsonResponse({"detail": "Missing sender or message identifier."}, status=HTTPStatus.BAD_REQUEST)

    defaults = {
        "project": project,
        "sender_email": sender_email,
        "subject": str(payload_data.get("subject", ""))[:512],
        "raw_html": sanitize_newsletter_html(str(payload_data.get("html", "") or payload_data.get("html_body", ""))),
        "raw_text": str(payload_data.get("text", "") or payload_data.get("text_body", "")),
    }
    intake, created = NewsletterIntake.objects.get_or_create(message_id=message_id, defaults=defaults)
    if not created:
        return JsonResponse({"id": intake.id, "status": intake.status, "duplicate": True}, status=HTTPStatus.OK)

    allowlist, allowlist_created = IntakeAllowlist.objects.get_or_create(
        project=project,
        sender_email=sender_email,
    )

    if allowlist.is_confirmed:
        _queue_newsletter_intake(intake.id)
        return JsonResponse({"id": intake.id, "status": intake.status}, status=HTTPStatus.ACCEPTED)

    if allowlist_created:
        confirm_url = request.build_absolute_uri(f"/api/v1/inbound/confirm/{allowlist.confirmation_token}/")
        send_confirmation_email(to_email=sender_email, confirm_url=confirm_url, project_name=project.name)

    return JsonResponse({"id": intake.id, "status": intake.status, "confirmation_required": True}, status=HTTPStatus.ACCEPTED)


@require_GET
def confirm_newsletter_sender_view(request: HttpRequest, token: str):
    allowlist = get_object_or_404(IntakeAllowlist, confirmation_token=token)
    if allowlist.confirmed_at is None:
        allowlist.confirmed_at = timezone.now()
        allowlist.save(update_fields=["confirmed_at"])

    pending_intake_ids = list(
        NewsletterIntake.objects.filter(
            project=allowlist.project,
            sender_email=allowlist.sender_email,
            status=NewsletterIntakeStatus.PENDING,
        ).values_list("id", flat=True)
    )
    for intake_id in pending_intake_ids:
        _queue_newsletter_intake(intake_id)

    return JsonResponse({"status": "confirmed", "queued": len(pending_intake_ids)})


def _extract_project_token_from_recipient(recipient: str) -> str | None:
    from core.newsletters import extract_project_token

    return extract_project_token(recipient)


def _queue_newsletter_intake(intake_id: int) -> None:
    if settings.CELERY_TASK_ALWAYS_EAGER:
        process_newsletter_intake(intake_id)
    else:
        process_newsletter_intake.delay(intake_id)
