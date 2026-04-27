from types import SimpleNamespace
from unittest.mock import ANY

import pytest
from django.contrib import messages
from django.contrib.admin.sites import AdminSite
from django.utils import timezone

from core.admin import ReviewQueueAdmin, SourceConfigAdmin
from core.models import Content, ReviewQueue, ReviewReason, SourceConfig, SourcePluginName, Tenant

pytestmark = pytest.mark.django_db


@pytest.fixture
def source_admin_context(django_user_model):
    user = django_user_model.objects.create_user(username="admin-owner", password="testpass123")
    tenant = Tenant.objects.create(name="Admin Tenant", user=user, topic_description="Infra")
    return SimpleNamespace(user=user, tenant=tenant)


def test_test_source_connection_reports_success(source_admin_context, mocker):
    source_config = SourceConfig.objects.create(
        tenant=source_admin_context.tenant,
        plugin_name=SourcePluginName.RSS,
        config={"feed_url": "https://example.com/feed.xml"},
    )
    plugin = mocker.Mock()
    plugin.health_check.return_value = True
    validate_mock = mocker.patch(
        "core.admin.validate_plugin_config",
        return_value={"feed_url": "https://example.com/feed.xml"},
    )
    get_plugin_mock = mocker.patch("core.admin.get_plugin_for_source_config", return_value=plugin)
    admin_instance = SourceConfigAdmin(SourceConfig, AdminSite())
    admin_instance.message_user = mocker.Mock()

    admin_instance.test_source_connection(
        request=SimpleNamespace(),
        queryset=SourceConfig.objects.filter(pk=source_config.pk),
    )

    validate_mock.assert_called_once_with(SourcePluginName.RSS, {"feed_url": "https://example.com/feed.xml"})
    get_plugin_mock.assert_called_once()
    plugin.health_check.assert_called_once_with()
    admin_instance.message_user.assert_called_once_with(
        ANY,
        "Connectivity check passed for 1 source(s).",
        messages.SUCCESS,
    )


def test_test_source_connection_reports_failures(source_admin_context, mocker):
    source_config = SourceConfig.objects.create(
        tenant=source_admin_context.tenant,
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
        "Connectivity check failed for: rss source for Admin Tenant: Missing required config field: feed_url",
        messages.ERROR,
    )


def test_review_queue_changelist_view_builds_dashboard_stats(source_admin_context, mocker):
    content = Content.objects.create(
        tenant=source_admin_context.tenant,
        url="https://example.com/review-item",
        title="Review Item",
        author="Reviewer",
        source_plugin=SourcePluginName.RSS,
        published_date=timezone.now(),
        content_text="Review queue content",
    )
    ReviewQueue.objects.create(
        tenant=source_admin_context.tenant,
        content=content,
        reason=ReviewReason.BORDERLINE_RELEVANCE,
        confidence=0.42,
        resolved=False,
    )
    admin_instance = ReviewQueueAdmin(ReviewQueue, AdminSite())
    mocker.patch.object(admin_instance, "get_queryset", return_value=ReviewQueue.objects.all())
    super_changelist_view = mocker.patch(
        "core.admin.ModelAdmin.changelist_view",
        side_effect=lambda request, extra_context=None: extra_context,
    )

    response = admin_instance.changelist_view(request=SimpleNamespace())

    super_changelist_view.assert_called_once()
    assert response["dashboard_stats"][0]["value"] == 1
    assert response["dashboard_stats"][1]["value"] == "42%"
