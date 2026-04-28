from django.urls import path

from core.views import confirm_newsletter_sender_view, healthz_view, readyz_view

urlpatterns = [
    path("healthz/", healthz_view, name="healthz"),
    path("readyz/", readyz_view, name="readyz"),
    path("api/v1/inbound/confirm/<str:token>/", confirm_newsletter_sender_view, name="confirm-newsletter-sender"),
]
