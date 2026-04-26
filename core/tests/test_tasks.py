from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from core.models import Content, Entity, IngestionRun, RunStatus, SourceConfig, SourcePluginName, Tenant
from core.tasks import run_all_ingestions, run_ingestion

pytestmark = pytest.mark.django_db


@pytest.fixture
def source_plugin_context(django_user_model):
    user = django_user_model.objects.create_user(username="plugin-owner", password="testpass123")
    tenant = Tenant.objects.create(name="Plugin Tenant", user=user, topic_description="Infra")
    entity = Entity.objects.create(
        tenant=tenant,
        name="Example",
        type="vendor",
        website_url="https://example.com",
    )
    return SimpleNamespace(user=user, tenant=tenant, entity=entity)


def test_run_ingestion_creates_content_from_rss_entries(source_plugin_context, mocker):
    upsert_embedding_mock = mocker.patch("core.tasks.upsert_content_embedding")
    process_content_delay_mock = mocker.patch("core.tasks.process_content.delay")
    parse_mock = mocker.patch("core.plugins.rss.feedparser.parse")
    source_config = SourceConfig.objects.create(
            tenant=source_plugin_context.tenant,
            plugin_name=SourcePluginName.RSS,
            config={"feed_url": "https://example.com/feed.xml"},
    )
    parse_mock.return_value = SimpleNamespace(
        entries=[
            SimpleNamespace(
                link="https://example.com/post-1",
                title="Example Post",
                author="Author",
                summary="Summary",
                published_parsed=datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc).timetuple(),
            )
        ]
    )

    result = run_ingestion(source_config.id)

    assert result["items_fetched"] == 1
    assert result["items_ingested"] == 1
    content = Content.objects.get(url="https://example.com/post-1")
    assert content.tenant == source_plugin_context.tenant
    assert content.entity == source_plugin_context.entity
    upsert_embedding_mock.assert_called_once_with(content)
    process_content_delay_mock.assert_called_once_with(content.id)
    assert SourceConfig.objects.get(pk=source_config.id).last_fetched_at is not None
    ingestion_run = IngestionRun.objects.get(tenant=source_plugin_context.tenant, plugin_name=SourcePluginName.RSS)
    assert ingestion_run.status == RunStatus.SUCCESS

def test_run_ingestion_skips_duplicate_urls(source_plugin_context, mocker):
    upsert_embedding_mock = mocker.patch("core.tasks.upsert_content_embedding")
    process_content_delay_mock = mocker.patch("core.tasks.process_content.delay")
    parse_mock = mocker.patch("core.plugins.rss.feedparser.parse")
    source_config = SourceConfig.objects.create(
            tenant=source_plugin_context.tenant,
            plugin_name=SourcePluginName.RSS,
            config={"feed_url": "https://example.com/feed.xml"},
    )
    Content.objects.create(
        tenant=source_plugin_context.tenant,
        entity=source_plugin_context.entity,
        url="https://example.com/post-1",
        title="Existing",
        author="Author",
        source_plugin=SourcePluginName.RSS,
        published_date="2026-04-20T12:00:00Z",
        content_text="Existing content",
    )
    parse_mock.return_value = SimpleNamespace(
        entries=[
            SimpleNamespace(
                link="https://example.com/post-1",
                title="Duplicate Post",
                author="Author",
                summary="Summary",
                published_parsed=datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc).timetuple(),
            )
        ]
    )

    result = run_ingestion(source_config.id)

    assert result["items_fetched"] == 1
    assert result["items_ingested"] == 0
    upsert_embedding_mock.assert_not_called()
    process_content_delay_mock.assert_not_called()
    assert Content.objects.filter(url="https://example.com/post-1").count() == 1

def test_run_ingestion_creates_content_from_reddit_posts(source_plugin_context, mocker):
    upsert_embedding_mock = mocker.patch("core.tasks.upsert_content_embedding")
    process_content_delay_mock = mocker.patch("core.tasks.process_content.delay")
    reddit_mock = mocker.patch("core.plugins.reddit.praw.Reddit")
    source_config = SourceConfig.objects.create(
            tenant=source_plugin_context.tenant,
            plugin_name=SourcePluginName.REDDIT,
            config={"subreddit": "python", "listing": "new", "limit": 5},
    )
    submission = SimpleNamespace(
        id="abc123",
        url="https://reddit.com/r/python/comments/abc123/test",
        permalink="/r/python/comments/abc123/test",
        title="Reddit Post",
        selftext="Post body",
        author="redditor",
        created_utc=datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc).timestamp(),
    )
    subreddit = SimpleNamespace(new=lambda limit: iter([submission]), hot=lambda limit: iter([]))
    reddit_mock.return_value.subreddit.return_value = subreddit

    result = run_ingestion(source_config.id)

    assert result["items_fetched"] == 1
    assert result["items_ingested"] == 1
    content = Content.objects.get(title="Reddit Post")
    upsert_embedding_mock.assert_called_once_with(content)
    process_content_delay_mock.assert_called_once_with(content.id)
    assert content.source_plugin == SourcePluginName.REDDIT
    assert content.entity is None

def test_run_all_ingestions_enqueues_active_source_configs(source_plugin_context, mocker):
    delay_mock = mocker.patch("core.tasks.run_ingestion.delay")
    active_one = SourceConfig.objects.create(
            tenant=source_plugin_context.tenant,
            plugin_name=SourcePluginName.RSS,
            config={"feed_url": "https://example.com/feed.xml"},
    )
    active_two = SourceConfig.objects.create(
        tenant=source_plugin_context.tenant,
        plugin_name=SourcePluginName.REDDIT,
        config={"subreddit": "python"},
    )
    SourceConfig.objects.create(
        tenant=source_plugin_context.tenant,
        plugin_name=SourcePluginName.RSS,
        config={"feed_url": "https://example.com/inactive.xml"},
        is_active=False,
    )

    enqueued_count = run_all_ingestions()

    assert enqueued_count == 2
    delay_mock.assert_any_call(active_one.id)
    delay_mock.assert_any_call(active_two.id)
    assert delay_mock.call_count == 2

def test_run_ingestion_marks_failure_when_plugin_errors(source_plugin_context, mocker):
    parse_mock = mocker.patch("core.plugins.rss.feedparser.parse")
    source_config = SourceConfig.objects.create(
            tenant=source_plugin_context.tenant,
            plugin_name=SourcePluginName.RSS,
            config={"feed_url": "https://example.com/feed.xml"},
    )
    parse_mock.side_effect = RuntimeError("feed unavailable")

    with pytest.raises(RuntimeError, match="feed unavailable"):
        run_ingestion(source_config.id)

    ingestion_run = IngestionRun.objects.get(tenant=source_plugin_context.tenant, plugin_name=SourcePluginName.RSS)
    assert ingestion_run.status == RunStatus.FAILED
    assert ingestion_run.error_message == "feed unavailable"
