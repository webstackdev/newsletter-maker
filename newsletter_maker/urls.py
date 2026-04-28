from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.shortcuts import redirect
from django.urls import include, path
from django.views.generic.base import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from core.auth_views import GitHubLoginView, GoogleLoginView


def root_redirect_view(request):
    return redirect("/admin/")

urlpatterns = [
    path("", include("core.urls")),
    path("", root_redirect_view),
    path("admin/", admin.site.urls),
    path("anymail/", include("anymail.urls")),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/auth/", include("dj_rest_auth.urls")),
    path("api/auth/registration/", include("dj_rest_auth.registration.urls")),
    path("api/auth/github/", GitHubLoginView.as_view(), name="github_login"),
    path("api/auth/google/", GoogleLoginView.as_view(), name="google_login"),
    path("api/v1/", include(("core.api_urls", "api"), namespace="v1")),
    path("favicon.ico", RedirectView.as_view(url="/static/core/favicon.ico", permanent=True)),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
