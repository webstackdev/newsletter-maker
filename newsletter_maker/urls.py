from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path
from django.views.generic.base import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


def root_redirect_view(request):
    return redirect("/admin/")

urlpatterns = [
    path("", root_redirect_view),
    path("admin/", admin.site.urls),
    path("favicon.ico", RedirectView.as_view(url="/static/core/favicon.ico", permanent=True)),
    path("api/v1/", include(("core.api_urls", "api"), namespace="v1")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("", include("core.urls")),
]
