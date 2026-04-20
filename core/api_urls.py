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
router.register("tenant-configs", TenantConfigViewSet, basename="tenant-config")
router.register("entities", EntityViewSet, basename="entity")
router.register("contents", ContentViewSet, basename="content")
router.register("skill-results", SkillResultViewSet, basename="skill-result")
router.register("feedback", UserFeedbackViewSet, basename="user-feedback")
router.register("ingestion-runs", IngestionRunViewSet, basename="ingestion-run")
router.register("review-queue", ReviewQueueViewSet, basename="review-queue")

urlpatterns = router.urls