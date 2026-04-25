from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Content, Entity, IngestionRun, RunStatus, SourceConfig, SourcePluginName, Tenant
from core.tasks import run_all_ingestions, run_ingestion


class SourcePluginTaskTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="plugin-owner", password="testpass123")
        self.tenant = Tenant.objects.create(name="Plugin Tenant", user=self.user, topic_description="Infra")
        self.entity = Entity.objects.create(
            tenant=self.tenant,
            name="Example",
            type="vendor",
            website_url="https://example.com",
        )

    @patch("core.tasks.upsert_content_embedding")
    @patch("core.plugins.rss.feedparser.parse")
    def test_run_ingestion_creates_content_from_rss_entries(self, parse_mock, upsert_embedding_mock):
        source_config = SourceConfig.objects.create(
            tenant=self.tenant,
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

        self.assertEqual(result["items_fetched"], 1)
        self.assertEqual(result["items_ingested"], 1)
        content = Content.objects.get(url="https://example.com/post-1")
        self.assertEqual(content.tenant, self.tenant)
        self.assertEqual(content.entity, self.entity)
        upsert_embedding_mock.assert_called_once_with(content)
        self.assertTrue(SourceConfig.objects.get(pk=source_config.id).last_fetched_at is not None)
        ingestion_run = IngestionRun.objects.get(tenant=self.tenant, plugin_name=SourcePluginName.RSS)
        self.assertEqual(ingestion_run.status, RunStatus.SUCCESS)

    @patch("core.tasks.upsert_content_embedding")
    @patch("core.plugins.rss.feedparser.parse")
    def test_run_ingestion_skips_duplicate_urls(self, parse_mock, upsert_embedding_mock):
        source_config = SourceConfig.objects.create(
            tenant=self.tenant,
            plugin_name=SourcePluginName.RSS,
            config={"feed_url": "https://example.com/feed.xml"},
        )
        Content.objects.create(
            tenant=self.tenant,
            entity=self.entity,
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

        self.assertEqual(result["items_fetched"], 1)
        self.assertEqual(result["items_ingested"], 0)
        upsert_embedding_mock.assert_not_called()
        self.assertEqual(Content.objects.filter(url="https://example.com/post-1").count(), 1)

    @patch("core.tasks.upsert_content_embedding")
    @patch("core.plugins.reddit.praw.Reddit")
    @patch("core.plugins.reddit.settings.REDDIT_CLIENT_SECRET", "secret")
    @patch("core.plugins.reddit.settings.REDDIT_CLIENT_ID", "client")
    def test_run_ingestion_creates_content_from_reddit_posts(self, reddit_mock, upsert_embedding_mock):
        source_config = SourceConfig.objects.create(
            tenant=self.tenant,
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

        self.assertEqual(result["items_fetched"], 1)
        self.assertEqual(result["items_ingested"], 1)
        content = Content.objects.get(title="Reddit Post")
        upsert_embedding_mock.assert_called_once_with(content)
        self.assertEqual(content.source_plugin, SourcePluginName.REDDIT)
        self.assertIsNone(content.entity)

    @patch("core.tasks.run_ingestion.delay")
    def test_run_all_ingestions_enqueues_active_source_configs(self, delay_mock):
        active_one = SourceConfig.objects.create(
            tenant=self.tenant,
            plugin_name=SourcePluginName.RSS,
            config={"feed_url": "https://example.com/feed.xml"},
        )
        active_two = SourceConfig.objects.create(
            tenant=self.tenant,
            plugin_name=SourcePluginName.REDDIT,
            config={"subreddit": "python"},
        )
        SourceConfig.objects.create(
            tenant=self.tenant,
            plugin_name=SourcePluginName.RSS,
            config={"feed_url": "https://example.com/inactive.xml"},
            is_active=False,
        )

        enqueued_count = run_all_ingestions()

        self.assertEqual(enqueued_count, 2)
        delay_mock.assert_any_call(active_one.id)
        delay_mock.assert_any_call(active_two.id)
        self.assertEqual(delay_mock.call_count, 2)

    @patch("core.plugins.rss.feedparser.parse")
    def test_run_ingestion_marks_failure_when_plugin_errors(self, parse_mock):
        source_config = SourceConfig.objects.create(
            tenant=self.tenant,
            plugin_name=SourcePluginName.RSS,
            config={"feed_url": "https://example.com/feed.xml"},
        )
        parse_mock.side_effect = RuntimeError("feed unavailable")

        with self.assertRaises(RuntimeError):
            run_ingestion(source_config.id)

        ingestion_run = IngestionRun.objects.get(tenant=self.tenant, plugin_name=SourcePluginName.RSS)
        self.assertEqual(ingestion_run.status, RunStatus.FAILED)
        self.assertEqual(ingestion_run.error_message, "feed unavailable")
