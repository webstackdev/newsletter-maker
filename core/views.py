from http import HTTPStatus
from typing import cast

from django.conf import settings as django_settings
from django.db import connection
from django.http import JsonResponse
from qdrant_client import QdrantClient

from core.settings_types import CoreSettings

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
