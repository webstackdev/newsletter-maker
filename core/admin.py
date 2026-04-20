from django.contrib import admin

from core.models import Content, Entity, IngestionRun, ReviewQueue, SkillResult, Tenant, TenantConfig, UserFeedback


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
	list_display = ("name", "user", "content_retention_days", "created_at")
	search_fields = ("name", "user__username")


@admin.register(TenantConfig)
class TenantConfigAdmin(admin.ModelAdmin):
	list_display = ("tenant", "upvote_authority_weight", "downvote_authority_weight", "authority_decay_rate")


@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
	list_display = ("name", "tenant", "type", "authority_score", "created_at")
	list_filter = ("type", "tenant")
	search_fields = ("name", "description")


@admin.register(Content)
class ContentAdmin(admin.ModelAdmin):
	list_display = ("title", "tenant", "source_plugin", "published_date", "relevance_score", "is_active")
	list_filter = ("tenant", "source_plugin", "is_active")
	search_fields = ("title", "author", "url")


@admin.register(SkillResult)
class SkillResultAdmin(admin.ModelAdmin):
	list_display = ("skill_name", "content", "tenant", "status", "model_used", "created_at")
	list_filter = ("status", "skill_name", "tenant")
	search_fields = ("skill_name", "content__title", "model_used")


@admin.register(UserFeedback)
class UserFeedbackAdmin(admin.ModelAdmin):
	list_display = ("content", "tenant", "user", "feedback_type", "created_at")
	list_filter = ("feedback_type", "tenant")


@admin.register(IngestionRun)
class IngestionRunAdmin(admin.ModelAdmin):
	list_display = ("plugin_name", "tenant", "status", "items_fetched", "items_ingested", "started_at")
	list_filter = ("plugin_name", "status", "tenant")


@admin.register(ReviewQueue)
class ReviewQueueAdmin(admin.ModelAdmin):
	list_display = ("content", "tenant", "reason", "confidence", "resolved", "created_at")
	list_filter = ("reason", "resolved", "tenant")
