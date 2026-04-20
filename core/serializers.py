from rest_framework import serializers

from core.models import Content, Entity, IngestionRun, ReviewQueue, SkillResult, Tenant, TenantConfig, UserFeedback


class TenantScopedSerializerMixin:
    def _filter_related_queryset(self, request):
        user = request.user
        if "tenant" in self.fields:
            self.fields["tenant"].queryset = Tenant.objects.filter(user=user)
        if "entity" in self.fields:
            self.fields["entity"].queryset = Entity.objects.filter(tenant__user=user)
        if "content" in self.fields:
            self.fields["content"].queryset = Content.objects.filter(tenant__user=user)
        if "superseded_by" in self.fields:
            self.fields["superseded_by"].queryset = SkillResult.objects.filter(tenant__user=user)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            self._filter_related_queryset(request)


class TenantSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Tenant
        fields = ["id", "name", "user", "topic_description", "content_retention_days", "created_at"]
        read_only_fields = ["id", "user", "created_at"]


class TenantConfigSerializer(TenantScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = TenantConfig
        fields = [
            "id",
            "tenant",
            "upvote_authority_weight",
            "downvote_authority_weight",
            "authority_decay_rate",
        ]
        read_only_fields = ["id"]


class EntitySerializer(TenantScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Entity
        fields = [
            "id",
            "tenant",
            "name",
            "type",
            "description",
            "authority_score",
            "website_url",
            "github_url",
            "linkedin_url",
            "bluesky_handle",
            "mastodon_handle",
            "twitter_handle",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ContentSerializer(TenantScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Content
        fields = [
            "id",
            "tenant",
            "url",
            "title",
            "author",
            "entity",
            "source_plugin",
            "content_type",
            "published_date",
            "ingested_at",
            "content_text",
            "relevance_score",
            "is_active",
        ]
        read_only_fields = ["id", "ingested_at"]

    def validate(self, attrs):
        tenant = attrs.get("tenant") or getattr(self.instance, "tenant", None)
        entity = attrs.get("entity") or getattr(self.instance, "entity", None)
        if tenant and entity and entity.tenant_id != tenant.id:
            raise serializers.ValidationError({"entity": "Entity must belong to the selected tenant."})
        return attrs


class SkillResultSerializer(TenantScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = SkillResult
        fields = [
            "id",
            "content",
            "tenant",
            "skill_name",
            "status",
            "result_data",
            "error_message",
            "model_used",
            "latency_ms",
            "confidence",
            "created_at",
            "superseded_by",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        tenant = attrs.get("tenant") or getattr(self.instance, "tenant", None)
        content = attrs.get("content") or getattr(self.instance, "content", None)
        if tenant and content and content.tenant_id != tenant.id:
            raise serializers.ValidationError({"content": "Content must belong to the selected tenant."})
        return attrs


class UserFeedbackSerializer(TenantScopedSerializerMixin, serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = UserFeedback
        fields = ["id", "content", "tenant", "user", "feedback_type", "created_at"]
        read_only_fields = ["id", "user", "created_at"]

    def validate(self, attrs):
        tenant = attrs.get("tenant") or getattr(self.instance, "tenant", None)
        content = attrs.get("content") or getattr(self.instance, "content", None)
        if tenant and content and content.tenant_id != tenant.id:
            raise serializers.ValidationError({"content": "Content must belong to the selected tenant."})
        return attrs


class IngestionRunSerializer(TenantScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = IngestionRun
        fields = [
            "id",
            "tenant",
            "plugin_name",
            "started_at",
            "completed_at",
            "status",
            "items_fetched",
            "items_ingested",
            "error_message",
        ]
        read_only_fields = ["id", "started_at"]


class ReviewQueueSerializer(TenantScopedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = ReviewQueue
        fields = ["id", "tenant", "content", "reason", "confidence", "created_at", "resolved", "resolution"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        tenant = attrs.get("tenant") or getattr(self.instance, "tenant", None)
        content = attrs.get("content") or getattr(self.instance, "content", None)
        if tenant and content and content.tenant_id != tenant.id:
            raise serializers.ValidationError({"content": "Content must belong to the selected tenant."})
        return attrs