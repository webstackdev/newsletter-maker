from django.urls import path

from core.views import healthz_view, readyz_view


urlpatterns = [
    path("healthz/", healthz_view, name="healthz"),
    path("readyz/", readyz_view, name="readyz"),
]