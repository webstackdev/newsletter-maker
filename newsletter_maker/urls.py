from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path


def root_redirect_view(request):
    return redirect("/admin/")

urlpatterns = [
    path("", root_redirect_view),
    path("admin/", admin.site.urls),
    path("api/v1/", include(("core.api_urls", "api"), namespace="v1")),
    path("", include("core.urls")),
]
