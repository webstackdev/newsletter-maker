import json

from django.contrib import admin, messages
from django.db.models import Avg
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from import_export.admin import ExportActionMixin
from unfold.admin import ModelAdmin

from core.models import (
  Content,
  Entity,
  IngestionRun,
  ReviewQueue,
  SkillResult,
  SourceConfig,
  Tenant,
  TenantConfig,
  UserFeedback,
)
from core.plugins import get_plugin_for_source_config, validate_plugin_config
from core.tasks import process_content


@admin.register(Tenant)
class TenantAdmin(ExportActionMixin, admin.ModelAdmin):
  list_display = ("name", "user", "content_retention_days", "created_at")

  # Better navigation
  date_hierarchy = "created_at"
  list_filter = ("created_at",)

  # Faster searching
  search_fields = ("name", "user__username", "user__email")

  # Performance for large user lists
  autocomplete_fields = ("user",)

  # Quick editing
  list_editable = ("content_retention_days",)


@admin.register(TenantConfig)
class TenantConfigAdmin(admin.ModelAdmin):
	list_display = ("tenant", "upvote_authority_weight", "downvote_authority_weight", "authority_decay_rate")


@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
  # Replace 'authority_score' with your new method name
  list_display = ("name", "tenant", "type", "colored_score", "created_at")

  @admin.display(description="Authority Score", ordering="authority_score")
  def colored_score(self, obj):
      # Choose a color based on the value
      if obj.authority_score >= 80:
          color = "green"
      elif obj.authority_score >= 50:
          color = "orange"
      else:
          color = "red"

      return format_html(
          '<span style="color: {}; font-weight: bold;">{}</span>',
          color,
          obj.authority_score,
      )


class HighValueFilter(admin.SimpleListFilter):
    title = 'Content Value'
    parameter_name = 'value_tier'

    def lookups(self, request, model_admin):
        return (
            ('high_value', '🔥 High Value (Score > 80 & Reference)'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'high_value':
            return queryset.filter(relevance_score__gt=80, is_reference=True)
        return queryset


@admin.register(Content)
class ContentAdmin(admin.ModelAdmin):
    list_display = (
        "display_relevance",
        "is_active",
        "is_reference",
        "preview_content",
        "source_plugin",
        "tenant",
        "title",
        "view_trace",
    )
    list_editable = ("is_reference", "is_active")
    list_filter = (
        HighValueFilter,
        ("tenant", admin.RelatedOnlyFieldListFilter),
        "source_plugin",
        "is_active"
    )
    search_fields = ("title", "author", "url")
    actions = ["generate_newsletter_ideas"]

    @admin.display(description="Preview")
    def preview_content(self, obj):
        """Adds a quick preview based on the stored content text."""
        preview_text = (obj.content_text or "").strip()
        if not preview_text:
            return "-"
        return format_html(
            '<span title="{}" style="cursor:pointer;">🔍 View</span>',
            preview_text[:500]
        )

    @admin.display(description="AI Trace")
    def view_trace(self, obj):
        """Link to the latest external trace when present, otherwise the internal skill run history."""
        from urllib.parse import urlencode

        from django.conf import settings
        from django.urls import reverse

        latest_skill_result = obj.skill_results.filter(
            superseded_by__isnull=True,
        ).order_by("-created_at").first()
        if latest_skill_result is None:
            return "-"

        result_data = latest_skill_result.result_data or {}
        trace_sections = [result_data]
        for section_name in ("trace", "langsmith", "langfuse", "observability", "telemetry"):
            section = result_data.get(section_name)
            if isinstance(section, dict):
                trace_sections.append(section)

        trace_url = ""
        trace_id = ""
        for section in trace_sections:
            for key in ("trace_url", "traceUrl", "langsmith_run_url", "langfuse_trace_url"):
                value = section.get(key)
                if isinstance(value, str) and value:
                    trace_url = value
                    break
            if trace_url:
                break
            for key in ("trace_id", "traceId", "run_id", "runId", "langsmith_run_id", "langfuse_trace_id"):
                value = section.get(key)
                if isinstance(value, str) and value:
                    trace_id = value
                    break

        if not trace_url and trace_id and getattr(settings, "AI_TRACE_URL_TEMPLATE", ""):
            trace_url = settings.AI_TRACE_URL_TEMPLATE.format(
                content_id=obj.id,
                run_id=trace_id,
                skill_name=latest_skill_result.skill_name,
                skill_result_id=latest_skill_result.id,
                tenant_id=obj.tenant_id,
                trace_id=trace_id,
            )

        if trace_url:
            link_label = "📈 Trace"
            link_title = f"Open external trace for {latest_skill_result.skill_name}"
        else:
            trace_url = "{}?{}".format(
                reverse("admin:core_skillresult_changelist"),
                urlencode({"content__id__exact": obj.id}),
            )
            link_label = "🧠 Skill runs"
            link_title = f"Open persisted skill runs for {obj.title}"

        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer" style="color: #a855f7; font-weight: bold;" title="{}">{}</a>',
            trace_url,
            link_title,
            link_label,
        )

    @admin.display(description="Score")
    def display_relevance(self, obj):
        if obj.relevance_score is None:
            return "-"
        color = "green" if obj.relevance_score > 75 else "orange" if obj.relevance_score > 40 else "red"
        return format_html('<b style="color: {};">{}%</b>', color, obj.relevance_score)

    def changelist_view(self, request, extra_context=None):
        queryset = self.get_queryset(request)
        metrics = queryset.aggregate(avg_score=Avg('relevance_score'))

        extra_context = extra_context or {}
        extra_context["dashboard_stats"] = [
            {
                "title": "Avg Relevance",
                "value": f"{metrics['avg_score'] or 0:.1f}%",
                "icon": "insights",
                "color": "success" if (metrics['avg_score'] or 0) > 70 else "warning",
            },
            {
                "title": "Total Filtered",
                "value": queryset.count(),
                "icon": "inventory_2",
            },
        ]

        return super().changelist_view(request, extra_context=extra_context)

    @admin.action(description="Generate Ideas for Newsletter")
    def generate_newsletter_ideas(self, request, queryset):
        content_ids = list(queryset.values_list("id", flat=True))
        for content_id in content_ids:
            process_content.delay(content_id)
        self.message_user(
            request,
            f"Successfully queued the pipeline for {len(content_ids)} items.",
            messages.SUCCESS,
        )


@admin.register(SkillResult)
class SkillResultAdmin(ModelAdmin):
    list_display = (
        "skill_name",
        "get_content_link",
        "display_status",
        "display_performance",
        "preview_json",
        "is_current",
        "model_used",
        "created_at",
    )
    list_filter = ("status", "skill_name", "tenant", "model_used")
    search_fields = ("skill_name", "content__title", "model_used", "error_message")
    actions = ["retry_selected_skills"]
    readonly_fields = ("pretty_result_data", "latency_ms", "created_at", "superseded_by")
    fieldsets = (
        ("Execution Details", {
            "fields": ("skill_name", "content", "tenant", "status", "model_used")
        }),
        ("AI Output", {
            "fields": ("pretty_result_data", "error_message"),
        }),
        ("Performance Metrics", {
            "fields": ("latency_ms", "confidence", "created_at", "superseded_by"),
        }),
    )

    @admin.action(description="Retry Selected Skills")
    def retry_selected_skills(self, request, queryset):
        """Resets status to PENDING and clears errors for retry by the worker."""
        updated = queryset.update(status="PENDING", error_message="")
        self.message_user(
            request,
            f"Successfully reset {updated} skills to PENDING for retry.",
            messages.SUCCESS
        )

    @admin.display(description="Result Preview")
    def preview_json(self, obj):
        """Link that triggers Unfold's detail view (can be opened in side-panel)."""
        if not obj.result_data:
            return "-"
        return format_html(
            '<a href="{}" class="font-bold text-primary-600">🔍 Preview</a>',
            f"{obj.pk}/change/"
        )

    @admin.display(description="Content")
    def get_content_link(self, obj):
        return obj.content.title[:30] + "..." if obj.content.title else "Untitled"

    @admin.display(description="Status")
    def display_status(self, obj):
        colors = {"COMPLETED": "green", "FAILED": "red", "PENDING": "orange"}
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">● {}</span>',
            color, obj.status
        )

    @admin.display(description="Perf / Conf")
    def display_performance(self, obj):
        latency = f"{obj.latency_ms}ms" if obj.latency_ms else "-"
        conf = f"{int(obj.confidence * 100)}%" if obj.confidence is not None else "-"
        return f"{latency} / {conf}"

    @admin.display(description="Current", boolean=True)
    def is_current(self, obj):
        return obj.superseded_by is None

    @admin.display(description="Result Data JSON")
    def pretty_result_data(self, obj):
        if not obj.result_data:
            return "No data available"
        formatted_json = json.dumps(obj.result_data, indent=4)
        return mark_safe(
            f'<pre style="background: #1e1e1e; color: #dcdcdc; padding: 15px; border-radius: 8px; overflow-x: auto; font-family: monospace; font-size: 13px;">'
            f'{formatted_json}'
            f'</pre>'
        )

    def changelist_view(self, request, extra_context=None):
        qs = self.get_queryset(request)
        extra_context = extra_context or {}
        metrics = qs.aggregate(avg_lat=Avg('latency_ms'))
        avg_latency = metrics['avg_lat'] or 0
        failure_count = qs.filter(status='FAILED').count()
        total_count = qs.count() or 1

        extra_context["dashboard_stats"] = [
            {
                "title": "Avg Latency",
                "value": f"{avg_latency:.0f}ms",
                "icon": "timer",
                "color": "warning" if avg_latency > 2000 else "success",
            },
            {
                "title": "Failure Rate",
                "value": f"{(failure_count / total_count) * 100:.1f}%",
                "icon": "error",
                "color": "danger" if failure_count > 0 else "success",
            },
        ]
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(UserFeedback)
class UserFeedbackAdmin(ModelAdmin):
    list_display = (
        "display_feedback",
        "get_content_title",
        "get_ai_score",
        "tenant",
        "user",
        "created_at"
    )
    list_filter = ("feedback_type", ("tenant", admin.RelatedOnlyFieldListFilter))
    search_fields = ("content__title", "user__email", "user__username")

    @admin.display(description="Type")
    def display_feedback(self, obj):
        if obj.feedback_type == "UPVOTE":
            return format_html('<span style="font-size: {}">{}</span>', "1.2rem", "👍")
        return format_html('<span style="font-size: {}">{}</span>', "1.2rem", "👎")

    @admin.display(description="Content Title")
    def get_content_title(self, obj):
        return obj.content.title[:50] + "..."

    @admin.display(description="AI Score")
    def get_ai_score(self, obj):
        """Displays the original AI score to compare with user feedback."""
        score = obj.content.relevance_score
        if score is None:
            return "-"
        color = "green" if score > 75 else "red" if score < 40 else "orange"
        return format_html('<b style="color: {};">{}%</b>', color, score)

    def changelist_view(self, request, extra_context=None):
        qs = self.get_queryset(request)
        extra_context = extra_context or {}
        upvotes = qs.filter(feedback_type="UPVOTE").count()
        total = qs.count() or 1
        approval_rate = (upvotes / total) * 100

        extra_context["dashboard_stats"] = [
            {
                "title": "Approval Rate",
                "value": f"{approval_rate:.1f}%",
                "icon": "thumb_up",
                "color": "success" if approval_rate > 80 else "warning",
            },
            {
                "title": "Total Feedback",
                "value": total,
                "icon": "forum",
            },
        ]
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(IngestionRun)
class IngestionRunAdmin(ModelAdmin):
    list_display = (
        "plugin_name",
        "tenant",
        "display_status",
        "display_efficiency",
        "display_duration",
        "started_at",
    )
    list_filter = ("plugin_name", "status", ("tenant", admin.RelatedOnlyFieldListFilter))
    search_fields = ("plugin_name", "error_message", "tenant__name")
    readonly_fields = ("display_duration", "started_at", "completed_at")
    fieldsets = (
        ("Run Info", {
            "fields": ("plugin_name", "tenant", "status")
        }),
        ("Data Metrics", {
            "fields": ("items_fetched", "items_ingested", "display_efficiency")
        }),
        ("Timing", {
            "fields": ("started_at", "completed_at", "display_duration")
        }),
        ("Logs", {
            "fields": ("error_message",),
            "classes": ("collapse",)
        }),
    )

    @admin.display(description="Status")
    def display_status(self, obj):
        colors = {"COMPLETED": "success", "FAILED": "danger", "RUNNING": "info"}
        return format_html(
            '<span class="unfold-badge {}">{}</span>',
            colors.get(obj.status, "warning"),
            obj.status
        )

    @admin.display(description="Efficiency (Ingested/Fetched)")
    def display_efficiency(self, obj):
        if obj.items_fetched == 0:
            return "0/0"
        percent = (obj.items_ingested / obj.items_fetched) * 100
        color = "green" if percent > 90 else "orange" if percent > 50 else "red"
        percent_label = f"({percent:.0f}%)"
        return format_html(
            '<b>{} / {}</b> <small style="color: {}">{}</small>',
            obj.items_ingested, obj.items_fetched, color, percent_label
        )

    @admin.display(description="Duration")
    def display_duration(self, obj):
        if not obj.completed_at:
            return "In Progress..."
        duration = obj.completed_at - obj.started_at
        seconds = duration.total_seconds()
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"

    def changelist_view(self, request, extra_context=None):
        qs = self.get_queryset(request)
        extra_context = extra_context or {}
        total_runs = qs.count()
        failed_runs = qs.filter(status="FAILED").count()
        total_ingested = sum(qs.values_list('items_ingested', flat=True))

        extra_context["dashboard_stats"] = [
            {
                "title": "Total Content Ingested",
                "value": f"{total_ingested:,}",
                "icon": "cloud_download",
            },
            {
                "title": "Success Rate",
                "value": f"{((total_runs - failed_runs) / (total_runs or 1)) * 100:.1f}%",
                "icon": "check_circle",
                "color": "success" if failed_runs == 0 else "warning",
            },
        ]
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(SourceConfig)
class SourceConfigAdmin(ModelAdmin):
    list_display = (
        "plugin_name",
        "tenant",
        "display_health",
        "is_active",
        "last_fetched_at",
    )
    list_filter = ("is_active", "plugin_name", ("tenant", admin.RelatedOnlyFieldListFilter))
    list_editable = ("is_active",)
    search_fields = ("plugin_name", "tenant__name")
    actions = ["test_source_connection"]
    readonly_fields = ("last_fetched_at", "pretty_config")
    fieldsets = (
        ("Core Settings", {
            "fields": ("plugin_name", "tenant", "is_active")
        }),
        ("Configuration", {
            "fields": ("pretty_config", "config"),
        }),
        ("Activity", {
            "fields": ("last_fetched_at",),
        }),
    )

    @admin.display(description="Status")
    def display_health(self, obj):
        if not obj.is_active:
            return format_html('<span style="color: {};">{}</span>', "gray", "● Paused")

        if obj.last_fetched_at:
            hours_since = (timezone.now() - obj.last_fetched_at).total_seconds() / 3600
            if hours_since > 24:
                return format_html('<span style="color: {};">{}</span>', "red", "● Stale")
            return format_html('<span style="color: {};">{}</span>', "green", "● Healthy")

        return format_html('<span style="color: {};">{}</span>', "orange", "● Never Run")

    @admin.display(description="Config Preview")
    def pretty_config(self, obj):
        """Displays the JSON config in a readable format."""
        if not obj.config:
            return "Empty"
        formatted_json = json.dumps(obj.config, indent=4)
        return mark_safe(f'<pre style="background: #1e1e1e; color: #dcdcdc; padding: 10px; border-radius: 5px; font-size: 12px;">{formatted_json}</pre>')

    @admin.action(description="Test Source Connectivity")
    def test_source_connection(self, request, queryset):
        """
        Custom action to trigger a dry-run fetch for the selected sources.
        """
        healthy_sources = []
        failed_sources = []

        for source_config in queryset.select_related("tenant"):
            try:
                source_config.config = validate_plugin_config(
                    source_config.plugin_name,
                    source_config.config,
                )
                plugin = get_plugin_for_source_config(source_config)
                if not plugin.health_check():
                    raise RuntimeError("Health check returned an unhealthy status.")
            except Exception as exc:
                failed_sources.append(f"{source_config}: {exc}")
            else:
                healthy_sources.append(str(source_config))

        if healthy_sources:
            self.message_user(
                request,
                f"Connectivity check passed for {len(healthy_sources)} source(s).",
                messages.SUCCESS,
            )

        if failed_sources:
            self.message_user(
                request,
                "Connectivity check failed for: " + "; ".join(failed_sources),
                messages.ERROR,
            )

    def changelist_view(self, request, extra_context=None):
        qs = self.get_queryset(request)
        extra_context = extra_context or {}
        active_count = qs.filter(is_active=True).count()
        total_count = qs.count() or 1

        extra_context["dashboard_stats"] = [
            {
                "title": "Active Sources",
                "value": f"{active_count} / {total_count}",
                "icon": "settings_input_component",
                "color": "success" if active_count == total_count else "warning",
            },
            {
                "title": "Plugin Variety",
                "value": qs.values('plugin_name').distinct().count(),
                "icon": "extension",
            },
        ]
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(ReviewQueue)
class ReviewQueueAdmin(ModelAdmin):
    list_display = (
        "get_content_title",
        "tenant",
        "reason",
        "display_confidence",
        "resolved",
        "resolution",
        "created_at",
    )
    list_filter = ("resolved", "reason", ("tenant", admin.RelatedOnlyFieldListFilter))
    list_editable = ("resolved", "resolution")
    actions = ["mark_as_approved", "mark_as_rejected"]

    @admin.display(description="Content")
    def get_content_title(self, obj):
        return obj.content.title[:50] + "..."

    @admin.display(description="Confidence")
    def display_confidence(self, obj):
        color = "red" if obj.confidence < 0.3 else "orange" if obj.confidence < 0.6 else "green"
        confidence_label = f"{obj.confidence * 100:.0f}%"
        return format_html('<b style="color: {}">{}</b>', color, confidence_label)

    @admin.action(description="Approve selected items")
    def mark_as_approved(self, request, queryset):
        queryset.update(resolved=True, resolution="APPROVED")
        self.message_user(request, "Selected items approved.", messages.SUCCESS)

    @admin.action(description="Reject selected items")
    def mark_as_rejected(self, request, queryset):
        queryset.update(resolved=True, resolution="REJECTED")
        self.message_user(request, "Selected items rejected.", messages.WARNING)

    def changelist_view(self, request, extra_context=None):
        qs = self.get_queryset(request)
        extra_context = extra_context or {}
        pending_count = qs.filter(resolved=False).count()
        avg_conf = qs.aggregate(avg_confidence=Avg("confidence"))["avg_confidence"] or 0

        extra_context["dashboard_stats"] = [
            {
                "title": "Pending Review",
                "value": pending_count,
                "icon": "pending_actions",
                "color": "danger" if pending_count > 10 else "success",
            },
            {
                "title": "Avg Confidence",
                "value": f"{avg_conf * 100:.0f}%",
                "icon": "psychology",
            },
        ]
        return super().changelist_view(request, extra_context=extra_context)
