from rest_framework.routers import DefaultRouter
from rest_framework_nested.routers import NestedSimpleRouter

from core.api import (
    ContentViewSet,
    EntityViewSet,
    IngestionRunViewSet,
    ReviewQueueViewSet,
    SkillResultViewSet,
    SourceConfigViewSet,
    TenantConfigViewSet,
    TenantViewSet,
    UserFeedbackViewSet,
)

app_name = "api"

router = DefaultRouter()
router.register("tenants", TenantViewSet, basename="tenant")

tenant_router = NestedSimpleRouter(router, r"tenants", lookup="tenant")
tenant_router.register(r"tenant-configs", TenantConfigViewSet, basename="tenant-config")
tenant_router.register(r"entities", EntityViewSet, basename="tenant-entity")
tenant_router.register(r"contents", ContentViewSet, basename="tenant-content")
tenant_router.register(r"skill-results", SkillResultViewSet, basename="tenant-skill-result")
tenant_router.register(r"feedback", UserFeedbackViewSet, basename="tenant-feedback")
tenant_router.register(r"ingestion-runs", IngestionRunViewSet, basename="tenant-ingestion-run")
tenant_router.register(r"source-configs", SourceConfigViewSet, basename="tenant-source-config")
tenant_router.register(r"review-queue", ReviewQueueViewSet, basename="tenant-review-queue")

urlpatterns = [
    *router.urls,
    *tenant_router.urls,
]
