from datetime import UTC, datetime
from time import struct_time
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import Group

from core.models import Project, SourceConfig, SourcePluginName
from core.plugins.rss import RSSSourcePlugin


pytestmark = pytest.mark.django_db


@pytest.fixture
def rss_context(django_user_model):
    user = django_user_model.objects.create_user(username="rss-owner", password="testpass123")
    group = Group.objects.create(name="rss-team")
    user.groups.add(group)
    project = Project.objects.create(name="RSS Project", group=group, topic_description="Infra")
    source_config = SourceConfig.objects.create(
        project=project,
        plugin_name=SourcePluginName.RSS,
        config={"feed_url": "https://example.com/feed.xml"},
    )
    return SimpleNamespace(project=project, source_config=source_config)


def test_rss_fetch_new_content_filters_invalid_and_old_entries(rss_context, mocker):
    now = datetime(2026, 4, 28, 12, 0, tzinfo=UTC)
    old_time = now.replace(day=27).timetuple()
    fresh_time = now.timetuple()
    parsed_feed = SimpleNamespace(
        entries=[
            SimpleNamespace(link="", title="Missing link", published_parsed=fresh_time),
            SimpleNamespace(link="https://example.com/no-title", title="   ", published_parsed=fresh_time),
            SimpleNamespace(link="https://example.com/old", title="Old", published_parsed=old_time),
            SimpleNamespace(
                link="https://example.com/fresh",
                title="  Fresh entry  ",
                author=" Author ",
                description="  Feed description  ",
                updated_parsed=fresh_time,
            ),
        ]
    )
    mocker.patch("core.plugins.rss.feedparser.parse", return_value=parsed_feed)
    plugin = RSSSourcePlugin(rss_context.source_config)

    items = plugin.fetch_new_content(since=datetime(2026, 4, 28, 11, 0, tzinfo=UTC))

    assert len(items) == 1
    assert items[0].url == "https://example.com/fresh"
    assert items[0].title == "Fresh entry"
    assert items[0].author == "Author"
    assert items[0].content_text == "Feed description"
    assert items[0].source_plugin == SourcePluginName.RSS


def test_rss_fetch_new_content_uses_title_when_summary_and_description_missing(rss_context, mocker):
    parsed_feed = SimpleNamespace(
        entries=[
            SimpleNamespace(
                link="https://example.com/title-only",
                title="Title Only",
                created_parsed=datetime(2026, 4, 28, 12, 0, tzinfo=UTC).timetuple(),
            )
        ]
    )
    mocker.patch("core.plugins.rss.feedparser.parse", return_value=parsed_feed)
    plugin = RSSSourcePlugin(rss_context.source_config)

    items = plugin.fetch_new_content(since=None)

    assert len(items) == 1
    assert items[0].content_text == "Title Only"


def test_rss_health_check_returns_false_for_empty_feed(rss_context, mocker):
    mocker.patch("core.plugins.rss.feedparser.parse", return_value=SimpleNamespace(entries=[]))
    plugin = RSSSourcePlugin(rss_context.source_config)

    assert plugin.health_check() is False


def test_struct_time_to_datetime_builds_utc_datetime():
    parsed_value = struct_time((2026, 4, 28, 12, 30, 45, 1, 118, -1))

    result = RSSSourcePlugin._struct_time_to_datetime(parsed_value)

    assert result == datetime(2026, 4, 28, 12, 30, 45, tzinfo=UTC)