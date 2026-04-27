from types import SimpleNamespace
from unittest.mock import ANY

import pytest
from django.contrib import messages
from django.contrib.admin.sites import AdminSite

from core.admin import SourceConfigAdmin
from core.models import SourceConfig, SourcePluginName, Tenant

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
