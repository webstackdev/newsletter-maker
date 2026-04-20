from django.urls import path
from rest_framework.routers import DefaultRouter

from core.api import (
    ContentViewSet,
    EntityViewSet,
    IngestionRunViewSet,
    ReviewQueueViewSet,
    SkillResultViewSet,
    TenantConfigViewSet,
    TenantViewSet,
    UserFeedbackViewSet,
)


app_name = "api"

router = DefaultRouter()
router.register("tenants", TenantViewSet, basename="tenant")

tenant_config_list = TenantConfigViewSet.as_view({"get": "list", "post": "create"})
tenant_config_detail = TenantConfigViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)
entity_list = EntityViewSet.as_view({"get": "list", "post": "create"})
entity_detail = EntityViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)
content_list = ContentViewSet.as_view({"get": "list", "post": "create"})
content_detail = ContentViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)
skill_result_list = SkillResultViewSet.as_view({"get": "list", "post": "create"})
skill_result_detail = SkillResultViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)
feedback_list = UserFeedbackViewSet.as_view({"get": "list", "post": "create"})
feedback_detail = UserFeedbackViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)
ingestion_run_list = IngestionRunViewSet.as_view({"get": "list", "post": "create"})
ingestion_run_detail = IngestionRunViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)
review_queue_list = ReviewQueueViewSet.as_view({"get": "list", "post": "create"})
review_queue_detail = ReviewQueueViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)

urlpatterns = [
    *router.urls,
    path("tenants/<int:tenant_id>/tenant-configs/", tenant_config_list, name="tenant-config-list"),
    path("tenants/<int:tenant_id>/tenant-configs/<int:pk>/", tenant_config_detail, name="tenant-config-detail"),
    path("tenants/<int:tenant_id>/entities/", entity_list, name="tenant-entity-list"),
    path("tenants/<int:tenant_id>/entities/<int:pk>/", entity_detail, name="tenant-entity-detail"),
    path("tenants/<int:tenant_id>/contents/", content_list, name="tenant-content-list"),
    path("tenants/<int:tenant_id>/contents/<int:pk>/", content_detail, name="tenant-content-detail"),
    path("tenants/<int:tenant_id>/skill-results/", skill_result_list, name="tenant-skill-result-list"),
    path("tenants/<int:tenant_id>/skill-results/<int:pk>/", skill_result_detail, name="tenant-skill-result-detail"),
    path("tenants/<int:tenant_id>/feedback/", feedback_list, name="tenant-feedback-list"),
    path("tenants/<int:tenant_id>/feedback/<int:pk>/", feedback_detail, name="tenant-feedback-detail"),
    path("tenants/<int:tenant_id>/ingestion-runs/", ingestion_run_list, name="tenant-ingestion-run-list"),
    path(
        "tenants/<int:tenant_id>/ingestion-runs/<int:pk>/",
        ingestion_run_detail,
        name="tenant-ingestion-run-detail",
    ),
    path("tenants/<int:tenant_id>/review-queue/", review_queue_list, name="tenant-review-queue-list"),
    path(
        "tenants/<int:tenant_id>/review-queue/<int:pk>/",
        review_queue_detail,
        name="tenant-review-queue-detail",
    ),
]