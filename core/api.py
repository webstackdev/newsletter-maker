from rest_framework import viewsets

from core.models import Content, Entity, IngestionRun, ReviewQueue, SkillResult, Tenant, TenantConfig, UserFeedback
from core.serializers import (
    ContentSerializer,
    EntitySerializer,
    IngestionRunSerializer,
    ReviewQueueSerializer,
    SkillResultSerializer,
    TenantConfigSerializer,
    TenantSerializer,
    UserFeedbackSerializer,
)


class TenantOwnedQuerysetMixin:
    queryset = None

    def get_queryset(self):
        queryset = self.queryset
        if queryset is None:
            raise AssertionError("queryset must be set on tenant-scoped viewsets")
        return queryset.filter(tenant__user=self.request.user)


class TenantViewSet(viewsets.ModelViewSet):
    serializer_class = TenantSerializer
    queryset = Tenant.objects.select_related("user")

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TenantConfigViewSet(TenantOwnedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = TenantConfigSerializer
    queryset = TenantConfig.objects.select_related("tenant")


class EntityViewSet(TenantOwnedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = EntitySerializer
    queryset = Entity.objects.select_related("tenant")


class ContentViewSet(TenantOwnedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = ContentSerializer
    queryset = Content.objects.select_related("tenant", "entity")


class SkillResultViewSet(TenantOwnedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = SkillResultSerializer
    queryset = SkillResult.objects.select_related("content", "tenant", "superseded_by")


class UserFeedbackViewSet(TenantOwnedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = UserFeedbackSerializer
    queryset = UserFeedback.objects.select_related("content", "tenant", "user")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class IngestionRunViewSet(TenantOwnedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = IngestionRunSerializer
    queryset = IngestionRun.objects.select_related("tenant")


class ReviewQueueViewSet(TenantOwnedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = ReviewQueueSerializer
    queryset = ReviewQueue.objects.select_related("content", "tenant")