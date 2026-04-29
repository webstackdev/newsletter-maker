from types import SimpleNamespace
from unittest.mock import ANY

import pytest
from django.contrib import messages
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Group
from django.utils import timezone

from core.admin import (
    BlueskyCredentialsAdmin,
    BlueskyCredentialsAdminForm,
    ContentAdmin,
    EntityAdmin,
    HighValueFilter,
    IngestionRunAdmin,
    ReviewQueueAdmin,
    SkillResultAdmin,
    SourceConfigAdmin,
    UserFeedbackAdmin,
)
from core.models import (
    BlueskyCredentials,
    Content,
    Entity,
    IngestionRun,
    Project,
    ReviewQueue,
    ReviewReason,
    RunStatus,
    SkillResult,
    SourceConfig,
    SourcePluginName,
    UserFeedback,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def source_admin_context(django_user_model):
    user = django_user_model.objects.create_user(
        username="admin-owner", password="testpass123"
    )
    group = Group.objects.create(name="admin-team")
    user.groups.add(group)
    project = Project.objects.create(
        name="Admin Project", group=group, topic_description="Infra"
    )
    return SimpleNamespace(user=user, group=group, project=project)


def test_test_source_connection_reports_success(source_admin_context, mocker):
    source_config = SourceConfig.objects.create(
        project=source_admin_context.project,
        plugin_name=SourcePluginName.RSS,
        config={"feed_url": "https://example.com/feed.xml"},
    )
    plugin = mocker.Mock()
    plugin.health_check.return_value = True
    validate_mock = mocker.patch(
        "core.admin.validate_plugin_config",
        return_value={"feed_url": "https://example.com/feed.xml"},
    )
    get_plugin_mock = mocker.patch(
        "core.admin.get_plugin_for_source_config", return_value=plugin
    )
    admin_instance = SourceConfigAdmin(SourceConfig, AdminSite())
    admin_instance.message_user = mocker.Mock()

    admin_instance.test_source_connection(
        request=SimpleNamespace(),
        queryset=SourceConfig.objects.filter(pk=source_config.pk),
    )

    validate_mock.assert_called_once_with(
        SourcePluginName.RSS, {"feed_url": "https://example.com/feed.xml"}
    )
    get_plugin_mock.assert_called_once()
    plugin.health_check.assert_called_once_with()
    admin_instance.message_user.assert_called_once_with(
        ANY,
        "Connectivity check passed for 1 source(s).",
        messages.SUCCESS,
    )


def test_test_source_connection_reports_failures(source_admin_context, mocker):
    source_config = SourceConfig.objects.create(
        project=source_admin_context.project,
        plugin_name=SourcePluginName.RSS,
        config={"feed_url": "https://example.com/feed.xml"},
    )
    mocker.patch(
        "core.admin.validate_plugin_config",
        side_effect=ValueError("Missing required config field: feed_url"),
    )
    admin_instance = SourceConfigAdmin(SourceConfig, AdminSite())
    admin_instance.message_user = mocker.Mock()

    admin_instance.test_source_connection(
        request=SimpleNamespace(),
        queryset=SourceConfig.objects.filter(pk=source_config.pk),
    )

    admin_instance.message_user.assert_called_once_with(
        ANY,
        "Connectivity check failed for: rss source for Admin Project: Missing required config field: feed_url",
        messages.ERROR,
    )


def test_source_config_display_health_renders_without_django6_format_html_error(
    source_admin_context,
):
    source_config = SourceConfig.objects.create(
        project=source_admin_context.project,
        plugin_name=SourcePluginName.RSS,
        config={"feed_url": "https://example.com/feed.xml"},
        is_active=True,
        last_fetched_at=timezone.now(),
    )
    admin_instance = SourceConfigAdmin(SourceConfig, AdminSite())

    rendered = admin_instance.display_health(source_config)

    assert "Healthy" in rendered


def test_review_queue_changelist_view_builds_dashboard_stats(
    source_admin_context, mocker
):
    content = Content.objects.create(
        project=source_admin_context.project,
        url="https://example.com/review-item",
        title="Review Item",
        author="Reviewer",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="Review queue content",
    )
    ReviewQueue.objects.create(
        project=source_admin_context.project,
        content=content,
        reason=ReviewReason.BORDERLINE_RELEVANCE,
        confidence=0.42,
        resolved=False,
    )
    admin_instance = ReviewQueueAdmin(ReviewQueue, AdminSite())
    mocker.patch.object(
        admin_instance, "get_queryset", return_value=ReviewQueue.objects.all()
    )
    super_changelist_view = mocker.patch(
        "core.admin.ModelAdmin.changelist_view",
        side_effect=lambda request, extra_context=None: extra_context,
    )

    response = admin_instance.changelist_view(request=SimpleNamespace())

    super_changelist_view.assert_called_once()
    assert response["dashboard_stats"][0]["value"] == 1
    assert response["dashboard_stats"][1]["value"] == "42%"


def test_review_queue_display_confidence_renders_without_django6_format_error(
    source_admin_context,
):
    content = Content.objects.create(
        project=source_admin_context.project,
        url="https://example.com/review-confidence",
        title="Review Confidence",
        author="Reviewer",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="Review queue content",
    )
    review_item = ReviewQueue.objects.create(
        project=source_admin_context.project,
        content=content,
        reason=ReviewReason.BORDERLINE_RELEVANCE,
        confidence=0.42,
        resolved=False,
    )
    admin_instance = ReviewQueueAdmin(ReviewQueue, AdminSite())

    rendered = admin_instance.display_confidence(review_item)

    assert "42%" in rendered


def test_bluesky_credentials_admin_form_encrypts_app_password(source_admin_context):
    form = BlueskyCredentialsAdminForm(
        data={
            "project": source_admin_context.project.id,
            "handle": "@Alice.BSKY.social",
            "credential_input": "app-password",
            "pds_url": "https://pds.example.com/xrpc/",
            "is_active": True,
        }
    )

    assert form.is_valid(), form.errors
    credentials = form.save()

    assert credentials.handle == "alice.bsky.social"
    assert credentials.pds_url == "https://pds.example.com"
    assert credentials.has_app_password() is True
    assert credentials.get_app_password() == "app-password"


def test_verify_selected_bluesky_credentials_reports_success(
    source_admin_context, mocker
):
    credentials = BlueskyCredentials.objects.create(
        project=source_admin_context.project,
        handle="alice.bsky.social",
        app_password_encrypted="ciphertext",
    )
    verify_mock = mocker.patch("core.plugins.bluesky.BlueskySourcePlugin.verify_credentials")
    admin_instance = BlueskyCredentialsAdmin(BlueskyCredentials, AdminSite())
    admin_instance.message_user = mocker.Mock()

    admin_instance.verify_selected_credentials(
        request=SimpleNamespace(),
        queryset=BlueskyCredentials.objects.filter(pk=credentials.pk),
    )

    verify_mock.assert_called_once_with(credentials)
    admin_instance.message_user.assert_called_once_with(
        ANY,
        "Credential verification passed for 1 account(s).",
        messages.SUCCESS,
    )


def test_verify_selected_bluesky_credentials_reports_failures(
    source_admin_context, mocker
):
    credentials = BlueskyCredentials.objects.create(
        project=source_admin_context.project,
        handle="alice.bsky.social",
        app_password_encrypted="ciphertext",
    )
    mocker.patch(
        "core.plugins.bluesky.BlueskySourcePlugin.verify_credentials",
        side_effect=RuntimeError("bad login"),
    )
    admin_instance = BlueskyCredentialsAdmin(BlueskyCredentials, AdminSite())
    admin_instance.message_user = mocker.Mock()

    admin_instance.verify_selected_credentials(
        request=SimpleNamespace(),
        queryset=BlueskyCredentials.objects.filter(pk=credentials.pk),
    )

    admin_instance.message_user.assert_called_once_with(
        ANY,
        "Credential verification failed for: Bluesky credentials for Admin Project: bad login",
        messages.ERROR,
    )


def test_ingestion_run_display_efficiency_renders_without_django6_format_error(
    source_admin_context,
):
    run = IngestionRun.objects.create(
        project=source_admin_context.project,
        plugin_name=SourcePluginName.RSS,
        status=RunStatus.SUCCESS,
        items_fetched=12,
        items_ingested=9,
    )
    admin_instance = IngestionRunAdmin(IngestionRun, AdminSite())

    rendered = admin_instance.display_efficiency(run)

    assert "75%" in rendered


def test_content_preview_uses_content_text(source_admin_context):
    content = Content.objects.create(
        project=source_admin_context.project,
        url="https://example.com/admin-preview",
        title="Admin Preview",
        author="Editor",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="A short preview from the content body.",
    )
    admin_instance = ContentAdmin(Content, AdminSite())

    preview = admin_instance.preview_content(content)

    assert 'title="A short preview from the content body."' in preview


def test_content_preview_returns_dash_when_content_text_blank(source_admin_context):
    content = Content.objects.create(
        project=source_admin_context.project,
        url="https://example.com/admin-preview-empty",
        title="Admin Preview Empty",
        author="Editor",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="   ",
    )
    admin_instance = ContentAdmin(Content, AdminSite())

    assert admin_instance.preview_content(content) == "-"


def test_content_view_trace_prefers_external_trace_url(source_admin_context):
    content = Content.objects.create(
        project=source_admin_context.project,
        url="https://example.com/admin-trace",
        title="Admin Trace",
        author="Editor",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="Trace content.",
    )
    SkillResult.objects.create(
        content=content,
        project=source_admin_context.project,
        skill_name="summarization",
        status="COMPLETED",
        result_data={"trace_url": "https://traces.example/run/123"},
    )
    admin_instance = ContentAdmin(Content, AdminSite())

    rendered = admin_instance.view_trace(content)

    assert "https://traces.example/run/123" in rendered
    assert "📈 Trace" in rendered


def test_content_view_trace_falls_back_to_skill_runs_changelist(source_admin_context):
    content = Content.objects.create(
        project=source_admin_context.project,
        url="https://example.com/admin-trace-fallback",
        title="Admin Trace Fallback",
        author="Editor",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="Trace fallback content.",
    )
    SkillResult.objects.create(
        content=content,
        project=source_admin_context.project,
        skill_name="relevance_scoring",
        status="COMPLETED",
        result_data={"relevance_score": 0.9},
    )
    admin_instance = ContentAdmin(Content, AdminSite())

    rendered = admin_instance.view_trace(content)

    assert "🧠 Skill runs" in rendered
    assert f"content__id__exact={content.id}" in rendered


def test_content_changelist_view_builds_dashboard_stats(source_admin_context, mocker):
    Content.objects.create(
        project=source_admin_context.project,
        url="https://example.com/admin-dashboard-1",
        title="Admin Dashboard 1",
        author="Editor",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="Content one.",
        relevance_score=80,
    )
    Content.objects.create(
        project=source_admin_context.project,
        url="https://example.com/admin-dashboard-2",
        title="Admin Dashboard 2",
        author="Editor",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="Content two.",
        relevance_score=40,
    )
    admin_instance = ContentAdmin(Content, AdminSite())
    mocker.patch.object(
        admin_instance, "get_queryset", return_value=Content.objects.all()
    )
    super_changelist_view = mocker.patch(
        "django.contrib.admin.options.ModelAdmin.changelist_view",
        side_effect=lambda request, extra_context=None: extra_context,
    )

    response = admin_instance.changelist_view(request=SimpleNamespace())

    super_changelist_view.assert_called_once()
    assert response["dashboard_stats"][0]["value"] == "60.0%"
    assert response["dashboard_stats"][1]["value"] == 2


def test_generate_newsletter_ideas_queues_selected_content(
    source_admin_context, mocker
):
    first_content = Content.objects.create(
        project=source_admin_context.project,
        url="https://example.com/admin-queue-1",
        title="Admin Queue 1",
        author="Editor",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="Queue one.",
    )
    second_content = Content.objects.create(
        project=source_admin_context.project,
        url="https://example.com/admin-queue-2",
        title="Admin Queue 2",
        author="Editor",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="Queue two.",
    )
    delay_mock = mocker.patch("core.tasks.process_content.delay")
    admin_instance = ContentAdmin(Content, AdminSite())
    admin_instance.message_user = mocker.Mock()

    admin_instance.generate_newsletter_ideas(
        request=SimpleNamespace(),
        queryset=Content.objects.filter(
            id__in=[first_content.id, second_content.id]
        ).order_by("id"),
    )

    delay_mock.assert_any_call(first_content.id)
    delay_mock.assert_any_call(second_content.id)
    assert delay_mock.call_count == 2
    admin_instance.message_user.assert_called_once_with(
        ANY,
        "Successfully queued the pipeline for 2 items.",
        messages.SUCCESS,
    )


@pytest.mark.parametrize(
    ("authority_score", "expected_color"),
    [
        (90, "green"),
        (60, "orange"),
        (20, "red"),
    ],
)
def test_entity_colored_score_uses_expected_color(
    source_admin_context, authority_score, expected_color
):
    entity = Entity.objects.create(
        project=source_admin_context.project,
        name=f"Entity {authority_score}",
        type="vendor",
        authority_score=authority_score,
        website_url=f"https://entity-{authority_score}.example.com",
    )
    admin_instance = EntityAdmin(Entity, AdminSite())

    rendered = admin_instance.colored_score(entity)

    assert expected_color in rendered
    assert str(authority_score) in rendered


def test_high_value_filter_only_returns_high_value_reference_content(
    source_admin_context,
):
    high_value = Content.objects.create(
        project=source_admin_context.project,
        url="https://example.com/high-value",
        title="High Value",
        author="Editor",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="High value content.",
        relevance_score=81,
        is_reference=True,
    )
    Content.objects.create(
        project=source_admin_context.project,
        url="https://example.com/not-high-value",
        title="Not High Value",
        author="Editor",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="Not high value content.",
        relevance_score=81,
        is_reference=False,
    )
    filter_instance = HighValueFilter(
        request=SimpleNamespace(GET={}),
        params={"value_tier": "high_value"},
        model=Content,
        model_admin=ContentAdmin(Content, AdminSite()),
    )
    filter_instance.value = lambda: "high_value"

    filtered = filter_instance.queryset(SimpleNamespace(), Content.objects.all())

    assert list(filtered) == [high_value]


def test_content_view_trace_builds_template_trace_url(source_admin_context, settings):
    settings.AI_TRACE_URL_TEMPLATE = "https://trace.example/{project_id}/{skill_name}/{skill_result_id}/{trace_id}/{content_id}/{run_id}"
    content = Content.objects.create(
        project=source_admin_context.project,
        url="https://example.com/admin-template-trace",
        title="Admin Template Trace",
        author="Editor",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="Template trace content.",
    )
    skill_result = SkillResult.objects.create(
        content=content,
        project=source_admin_context.project,
        skill_name="summarization",
        status="COMPLETED",
        result_data={"trace": {"trace_id": "trace-123"}},
    )
    admin_instance = ContentAdmin(Content, AdminSite())

    rendered = admin_instance.view_trace(content)

    assert (
        f"https://trace.example/{content.project_id}/summarization/{skill_result.id}/trace-123/{content.id}/trace-123"
        in rendered
    )


@pytest.mark.parametrize(
    ("score", "expected_color"),
    [
        (None, None),
        (80, "green"),
        (50, "orange"),
        (10, "red"),
    ],
)
def test_content_display_relevance_uses_expected_output(
    source_admin_context, score, expected_color
):
    content = Content.objects.create(
        project=source_admin_context.project,
        url=f"https://example.com/relevance-{score}",
        title="Relevance Display",
        author="Editor",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="Content.",
        relevance_score=score,
    )
    admin_instance = ContentAdmin(Content, AdminSite())

    rendered = admin_instance.display_relevance(content)

    if score is None:
        assert rendered == "-"
    else:
        assert expected_color in rendered
        assert str(score) in rendered


def test_skill_result_admin_helpers_and_dashboard_stats(source_admin_context, mocker):
    content = Content.objects.create(
        project=source_admin_context.project,
        url="https://example.com/skill-result",
        title="Skill Result Title For Preview",
        author="Editor",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="Skill result content.",
    )
    current_result = SkillResult.objects.create(
        content=content,
        project=source_admin_context.project,
        skill_name="summarization",
        status="FAILED",
        result_data={"summary": "Draft summary"},
        error_message="boom",
        latency_ms=1250,
        confidence=0.42,
    )
    superseded_result = SkillResult.objects.create(
        content=content,
        project=source_admin_context.project,
        skill_name="relevance_scoring",
        status="COMPLETED",
        result_data=None,
        latency_ms=250,
        confidence=0.91,
        superseded_by=current_result,
    )
    admin_instance = SkillResultAdmin(SkillResult, AdminSite())
    admin_instance.message_user = mocker.Mock()
    super_changelist_view = mocker.patch(
        "core.admin.ModelAdmin.changelist_view",
        side_effect=lambda request, extra_context=None: extra_context,
    )

    admin_instance.retry_selected_skills(
        SimpleNamespace(), SkillResult.objects.filter(pk=current_result.pk)
    )
    current_result.refresh_from_db()
    response = admin_instance.changelist_view(SimpleNamespace())

    assert current_result.status == "pending"
    assert current_result.error_message == ""
    admin_instance.message_user.assert_called_once_with(
        ANY,
        "Successfully reset 1 skills to PENDING for retry.",
        messages.SUCCESS,
    )
    assert (
        admin_instance.preview_json(current_result)
        == f'<a href="{current_result.pk}/change/" class="font-bold text-primary-600">🔍 Preview</a>'
    )
    assert admin_instance.preview_json(superseded_result) == "-"
    assert admin_instance.get_content_link(current_result).endswith("...")
    assert "● PENDING" in admin_instance.display_status(current_result)
    assert admin_instance.display_performance(current_result) == "1250ms / 42%"
    assert admin_instance.is_current(current_result) is True
    assert admin_instance.is_current(superseded_result) is False
    assert "Draft summary" in admin_instance.pretty_result_data(current_result)
    assert admin_instance.pretty_result_data(superseded_result) == "No data available"
    super_changelist_view.assert_called_once()
    assert response["dashboard_stats"][0]["value"] == "750ms"
    assert response["dashboard_stats"][1]["value"] == "0.0%"


def test_user_feedback_admin_helpers_and_dashboard_stats(
    source_admin_context, django_user_model, mocker
):
    user = django_user_model.objects.create_user(
        username="feedback-user", password="testpass123"
    )
    content = Content.objects.create(
        project=source_admin_context.project,
        url="https://example.com/feedback",
        title="Feedback Title That Is Long Enough To Truncate",
        author="Editor",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="Feedback content.",
        relevance_score=85,
    )
    upvote = UserFeedback.objects.create(
        content=content,
        project=source_admin_context.project,
        user=user,
        feedback_type="upvote",
    )
    other_content = Content.objects.create(
        project=source_admin_context.project,
        url="https://example.com/feedback-other",
        title="Other Feedback Title",
        author="Editor",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="Other feedback content.",
        relevance_score=20,
    )
    UserFeedback.objects.create(
        content=other_content,
        project=source_admin_context.project,
        user=django_user_model.objects.create_user(
            username="feedback-user-2", password="testpass123"
        ),
        feedback_type="downvote",
    )
    admin_instance = UserFeedbackAdmin(UserFeedback, AdminSite())
    super_changelist_view = mocker.patch(
        "core.admin.ModelAdmin.changelist_view",
        side_effect=lambda request, extra_context=None: extra_context,
    )

    response = admin_instance.changelist_view(SimpleNamespace())

    assert "👍" in admin_instance.display_feedback(upvote)
    assert admin_instance.get_content_title(upvote).endswith("...")
    assert "green" in admin_instance.get_ai_score(upvote)
    other_content.relevance_score = None
    other_content.save(update_fields=["relevance_score"])
    downvote = UserFeedback.objects.get(content=other_content)
    assert admin_instance.get_ai_score(downvote) == "-"
    super_changelist_view.assert_called_once()
    assert response["dashboard_stats"][0]["value"] == "50.0%"
    assert response["dashboard_stats"][1]["value"] == 2


def test_ingestion_run_display_duration_handles_running_and_completed(
    source_admin_context,
):
    running_run = IngestionRun.objects.create(
        project=source_admin_context.project,
        plugin_name=SourcePluginName.RSS,
        status=RunStatus.RUNNING,
        items_fetched=0,
        items_ingested=0,
    )
    completed_run = IngestionRun.objects.create(
        project=source_admin_context.project,
        plugin_name=SourcePluginName.RSS,
        status=RunStatus.SUCCESS,
        items_fetched=10,
        items_ingested=10,
    )
    completed_run.started_at = timezone.now() - timezone.timedelta(minutes=3, seconds=5)
    completed_run.completed_at = completed_run.started_at + timezone.timedelta(
        minutes=3, seconds=5
    )
    completed_run.save(update_fields=["started_at", "completed_at"])
    admin_instance = IngestionRunAdmin(IngestionRun, AdminSite())

    assert admin_instance.display_duration(running_run) == "In Progress..."
    assert admin_instance.display_duration(completed_run) == "3m 5s"


def test_review_queue_actions_update_resolution_and_emit_message(
    source_admin_context, mocker
):
    content = Content.objects.create(
        project=source_admin_context.project,
        url="https://example.com/review-action",
        title="Review Action",
        author="Reviewer",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="Review action content.",
    )
    approve_item = ReviewQueue.objects.create(
        project=source_admin_context.project,
        content=content,
        reason=ReviewReason.BORDERLINE_RELEVANCE,
        confidence=0.5,
        resolved=False,
    )
    reject_item = ReviewQueue.objects.create(
        project=source_admin_context.project,
        content=content,
        reason=ReviewReason.LOW_CONFIDENCE_CLASSIFICATION,
        confidence=0.2,
        resolved=False,
    )
    admin_instance = ReviewQueueAdmin(ReviewQueue, AdminSite())
    admin_instance.message_user = mocker.Mock()

    admin_instance.mark_as_approved(
        SimpleNamespace(), ReviewQueue.objects.filter(pk=approve_item.pk)
    )
    admin_instance.mark_as_rejected(
        SimpleNamespace(), ReviewQueue.objects.filter(pk=reject_item.pk)
    )

    approve_item.refresh_from_db()
    reject_item.refresh_from_db()
    assert approve_item.resolved is True
    assert approve_item.resolution == "APPROVED"
    assert reject_item.resolved is True
    assert reject_item.resolution == "REJECTED"
    assert admin_instance.message_user.call_count == 2


def test_high_value_filter_lookups_and_noop_queryset(source_admin_context):
    filter_instance = HighValueFilter(
        request=SimpleNamespace(GET={}),
        params={},
        model=Content,
        model_admin=ContentAdmin(Content, AdminSite()),
    )
    filter_instance.value = lambda: None
    content = Content.objects.create(
        project=source_admin_context.project,
        url="https://example.com/high-value-noop",
        title="Noop",
        author="Editor",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="noop",
    )

    assert filter_instance.lookups(None, None) == (
        ("high_value", "🔥 High Value (Score > 80 & Reference)"),
    )
    assert list(filter_instance.queryset(SimpleNamespace(), Content.objects.all())) == [
        content
    ]


def test_content_view_trace_returns_dash_when_no_skill_results(source_admin_context):
    content = Content.objects.create(
        project=source_admin_context.project,
        url="https://example.com/admin-no-trace",
        title="No Trace",
        author="Editor",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="No trace content.",
    )
    admin_instance = ContentAdmin(Content, AdminSite())

    assert admin_instance.view_trace(content) == "-"


def test_skill_result_admin_handles_unknown_status_and_empty_performance(
    source_admin_context,
):
    content = Content.objects.create(
        project=source_admin_context.project,
        url="https://example.com/skill-result-empty",
        title="",
        author="Editor",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="Skill result content.",
    )
    skill_result = SkillResult.objects.create(
        content=content,
        project=source_admin_context.project,
        skill_name="summarization",
        status="QUEUED",
        result_data={"summary": "Queued summary"},
        latency_ms=None,
        confidence=None,
    )
    admin_instance = SkillResultAdmin(SkillResult, AdminSite())

    assert admin_instance.get_content_link(skill_result) == "Untitled"
    assert "gray" in admin_instance.display_status(skill_result)
    assert admin_instance.display_performance(skill_result) == "- / -"


def test_skill_result_changelist_view_uses_warning_and_danger_colors(
    source_admin_context, mocker
):
    content = Content.objects.create(
        project=source_admin_context.project,
        url="https://example.com/skill-result-slow",
        title="Slow Skill Result",
        author="Editor",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="Slow skill result content.",
    )
    SkillResult.objects.create(
        content=content,
        project=source_admin_context.project,
        skill_name="summarization",
        status="failed",
        latency_ms=3001,
    )
    admin_instance = SkillResultAdmin(SkillResult, AdminSite())
    super_changelist_view = mocker.patch(
        "core.admin.ModelAdmin.changelist_view",
        side_effect=lambda request, extra_context=None: extra_context,
    )

    response = admin_instance.changelist_view(SimpleNamespace())

    super_changelist_view.assert_called_once()
    assert response["dashboard_stats"][0]["color"] == "warning"
    assert response["dashboard_stats"][1]["color"] == "danger"


def test_user_feedback_admin_upvote_and_orange_score_branches(source_admin_context):
    content = Content.objects.create(
        project=source_admin_context.project,
        url="https://example.com/feedback-orange",
        title="Orange Feedback Title",
        author="Editor",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="Feedback content.",
        relevance_score=60,
    )
    feedback = UserFeedback.objects.create(
        content=content,
        project=source_admin_context.project,
        user=source_admin_context.user,
        feedback_type="upvote",
    )
    admin_instance = UserFeedbackAdmin(UserFeedback, AdminSite())

    assert "👍" in admin_instance.display_feedback(feedback)
    assert "orange" in admin_instance.get_ai_score(feedback)


def test_user_feedback_changelist_view_uses_success_color_for_high_approval(
    source_admin_context, django_user_model, mocker
):
    first_content = Content.objects.create(
        project=source_admin_context.project,
        url="https://example.com/feedback-success-1",
        title="Feedback Success One",
        author="Editor",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="Feedback content one.",
        relevance_score=90,
    )
    second_content = Content.objects.create(
        project=source_admin_context.project,
        url="https://example.com/feedback-success-2",
        title="Feedback Success Two",
        author="Editor",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="Feedback content two.",
        relevance_score=90,
    )
    UserFeedback.objects.create(
        content=first_content,
        project=source_admin_context.project,
        user=source_admin_context.user,
        feedback_type="upvote",
    )
    UserFeedback.objects.create(
        content=second_content,
        project=source_admin_context.project,
        user=django_user_model.objects.create_user(
            username="feedback-success-2", password="testpass123"
        ),
        feedback_type="upvote",
    )
    admin_instance = UserFeedbackAdmin(UserFeedback, AdminSite())
    super_changelist_view = mocker.patch(
        "core.admin.ModelAdmin.changelist_view",
        side_effect=lambda request, extra_context=None: extra_context,
    )

    response = admin_instance.changelist_view(SimpleNamespace())

    super_changelist_view.assert_called_once()
    assert response["dashboard_stats"][0]["color"] == "success"
    assert response["dashboard_stats"][0]["value"] == "100.0%"


def test_ingestion_run_admin_status_efficiency_and_dashboard_branches(
    source_admin_context, mocker
):
    IngestionRun.objects.create(
        project=source_admin_context.project,
        plugin_name=SourcePluginName.RSS,
        status="failed",
        items_fetched=0,
        items_ingested=0,
    )
    running_run = IngestionRun.objects.create(
        project=source_admin_context.project,
        plugin_name=SourcePluginName.RSS,
        status=RunStatus.RUNNING,
        items_fetched=5,
        items_ingested=5,
    )
    admin_instance = IngestionRunAdmin(IngestionRun, AdminSite())
    super_changelist_view = mocker.patch(
        "core.admin.ModelAdmin.changelist_view",
        side_effect=lambda request, extra_context=None: extra_context,
    )

    response = admin_instance.changelist_view(SimpleNamespace())

    assert "danger" in admin_instance.display_status(
        IngestionRun.objects.filter(status="failed").first()
    )
    assert (
        admin_instance.display_efficiency(
            IngestionRun.objects.filter(status="failed").first()
        )
        == "0/0"
    )
    assert "info" in admin_instance.display_status(running_run)
    super_changelist_view.assert_called_once()
    assert response["dashboard_stats"][0]["value"] == "5"
    assert response["dashboard_stats"][1]["color"] == "warning"


def test_source_config_admin_health_pretty_config_and_dashboard_branches(
    source_admin_context, mocker
):
    stale_config = SourceConfig.objects.create(
        project=source_admin_context.project,
        plugin_name=SourcePluginName.RSS,
        config={"feed_url": "https://example.com/stale.xml"},
        is_active=True,
        last_fetched_at=timezone.now() - timezone.timedelta(days=2),
    )
    paused_config = SourceConfig.objects.create(
        project=source_admin_context.project,
        plugin_name=SourcePluginName.REDDIT,
        config={},
        is_active=False,
    )
    never_run_config = SourceConfig.objects.create(
        project=source_admin_context.project,
        plugin_name=SourcePluginName.RSS,
        config={},
        is_active=True,
        last_fetched_at=None,
    )
    admin_instance = SourceConfigAdmin(SourceConfig, AdminSite())
    super_changelist_view = mocker.patch(
        "core.admin.ModelAdmin.changelist_view",
        side_effect=lambda request, extra_context=None: extra_context,
    )

    response = admin_instance.changelist_view(SimpleNamespace())

    assert "Stale" in admin_instance.display_health(stale_config)
    assert "Paused" in admin_instance.display_health(paused_config)
    assert "Never Run" in admin_instance.display_health(never_run_config)
    assert admin_instance.pretty_config(paused_config) == "Empty"
    super_changelist_view.assert_called_once()
    assert response["dashboard_stats"][0]["color"] == "warning"
    assert response["dashboard_stats"][1]["value"] == 2


@pytest.mark.parametrize(
    ("confidence", "expected_color"),
    [
        (0.2, "red"),
        (0.9, "green"),
    ],
)
def test_review_queue_display_confidence_remaining_color_branches(
    source_admin_context,
    confidence,
    expected_color,
):
    content = Content.objects.create(
        project=source_admin_context.project,
        url=f"https://example.com/review-confidence-{confidence}",
        title="Review Confidence Remaining",
        author="Reviewer",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="Review queue content",
    )
    review_item = ReviewQueue.objects.create(
        project=source_admin_context.project,
        content=content,
        reason=ReviewReason.BORDERLINE_RELEVANCE,
        confidence=confidence,
        resolved=False,
    )
    admin_instance = ReviewQueueAdmin(ReviewQueue, AdminSite())

    rendered = admin_instance.display_confidence(review_item)

    assert expected_color in rendered
