from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(("core.api_urls", "api"), namespace="v1")),
    path("", include("core.urls")),
]
