from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core import embeddings
from core.embeddings import get_embedding_provider, get_reference_similarity, search_similar, search_similar_content, upsert_content_embedding
from core.models import Content, Entity, FeedbackType, Tenant, UserFeedback
from core.models import IngestionRun, ReviewQueue, ReviewReason, RunStatus, SkillResult, SkillStatus, SourceConfig, SourcePluginName, TenantConfig
from core.tasks import run_all_ingestions, run_ingestion


class HealthCheckTests(TestCase):
    def test_root_redirects_to_admin(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/admin/")

    def test_healthz_returns_ok(self):
        response = self.client.get("/healthz/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    @patch("core.views._check_database", return_value=True)
    @patch("core.views._check_qdrant", return_value=True)
    def test_readyz_returns_ok_when_dependencies_are_ready(self, qdrant_check, database_check):
        response = self.client.get("/readyz/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["checks"], {"database": True, "qdrant": True})

    @patch("core.views._check_database", return_value=True)
    @patch("core.views._check_qdrant", return_value=False)
    def test_readyz_returns_service_unavailable_when_dependency_fails(self, qdrant_check, database_check):
        response = self.client.get("/readyz/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "degraded")


class TenantScopedApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="owner", password="testpass123")
        self.other_user = user_model.objects.create_user(username="other", password="testpass123")
        self.owner_tenant = Tenant.objects.create(
            name="Owner Tenant",
            user=self.owner,
            topic_description="Platform engineering",
        )
        self.other_tenant = Tenant.objects.create(
            name="Other Tenant",
            user=self.other_user,
            topic_description="Frontend",
        )
        self.owner_entity = Entity.objects.create(
            tenant=self.owner_tenant,
            name="Owner Entity",
            type="individual",
        )
        self.other_entity = Entity.objects.create(
            tenant=self.other_tenant,
            name="Other Entity",
            type="vendor",
        )
        self.owner_content = Content.objects.create(
            tenant=self.owner_tenant,
            url="https://example.com/owner",
            title="Owner Content",
            author="Owner Author",
            entity=self.owner_entity,
            source_plugin="rss",
            published_date="2026-04-21T00:00:00Z",
            content_text="Owner content text",
        )
        self.other_content = Content.objects.create(
            tenant=self.other_tenant,
            url="https://example.com/other",
            title="Other Content",
            author="Other Author",
            entity=self.other_entity,
            source_plugin="rss",
            published_date="2026-04-21T00:00:00Z",
            content_text="Other content text",
        )
        self.owner_config = TenantConfig.objects.create(tenant=self.owner_tenant)
        self.owner_skill_result = SkillResult.objects.create(
            tenant=self.owner_tenant,
            content=self.owner_content,
            skill_name="summarization",
            status=SkillStatus.COMPLETED,
            result_data={"summary": "Owner summary"},
        )
        self.owner_ingestion_run = IngestionRun.objects.create(
            tenant=self.owner_tenant,
            plugin_name="rss",
            status=RunStatus.SUCCESS,
            items_fetched=5,
            items_ingested=4,
        )
        self.owner_review_queue = ReviewQueue.objects.create(
            tenant=self.owner_tenant,
            content=self.owner_content,
            reason=ReviewReason.BORDERLINE_RELEVANCE,
            confidence=0.51,
        )
        self.owner_source_config = SourceConfig.objects.create(
            tenant=self.owner_tenant,
            plugin_name=SourcePluginName.RSS,
            config={"feed_url": "https://example.com/feed.xml"},
        )
        self.client.force_authenticate(self.owner)

    def test_tenant_list_is_scoped_to_request_user(self):
        response = self.client.get(reverse("v1:tenant-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["id"], self.owner_tenant.id)

    def test_entity_list_is_scoped_to_request_user_tenant(self):
        response = self.client.get(reverse("v1:tenant-entity-list", kwargs={"tenant_id": self.owner_tenant.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["id"], self.owner_entity.id)

    def test_nested_entity_list_rejects_other_users_tenant(self):
        response = self.client.get(reverse("v1:tenant-entity-list", kwargs={"tenant_id": self.other_tenant.id}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_feedback_create_assigns_current_user(self):
        response = self.client.post(
            reverse("v1:tenant-feedback-list", kwargs={"tenant_id": self.owner_tenant.id}),
            {
                "content": self.owner_content.id,
                "feedback_type": FeedbackType.UPVOTE,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        feedback = UserFeedback.objects.get()
        self.assertEqual(feedback.user, self.owner)
        self.assertEqual(feedback.feedback_type, FeedbackType.UPVOTE)

    def test_feedback_rejects_cross_tenant_content(self):
        response = self.client.post(
            reverse("v1:tenant-feedback-list", kwargs={"tenant_id": self.owner_tenant.id}),
            {
                "content": self.other_content.id,
                "feedback_type": FeedbackType.DOWNVOTE,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("content", response.json())

    def test_content_create_uses_tenant_from_url(self):
        response = self.client.post(
            reverse("v1:tenant-content-list", kwargs={"tenant_id": self.owner_tenant.id}),
            {
                "url": "https://example.com/new",
                "title": "New Content",
                "author": "Owner Author",
                "entity": self.owner_entity.id,
                "source_plugin": "rss",
                "published_date": "2026-04-22T00:00:00Z",
                "content_text": "Nested content text",
                "tenant": self.other_tenant.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_content = Content.objects.get(title="New Content")
        self.assertEqual(created_content.tenant, self.owner_tenant)

    def test_authenticated_nested_list_endpoints_smoke(self):
        list_endpoints = [
            reverse("v1:tenant-config-list", kwargs={"tenant_id": self.owner_tenant.id}),
            reverse("v1:tenant-entity-list", kwargs={"tenant_id": self.owner_tenant.id}),
            reverse("v1:tenant-content-list", kwargs={"tenant_id": self.owner_tenant.id}),
            reverse("v1:tenant-skill-result-list", kwargs={"tenant_id": self.owner_tenant.id}),
            reverse("v1:tenant-feedback-list", kwargs={"tenant_id": self.owner_tenant.id}),
            reverse("v1:tenant-ingestion-run-list", kwargs={"tenant_id": self.owner_tenant.id}),
            reverse("v1:tenant-source-config-list", kwargs={"tenant_id": self.owner_tenant.id}),
            reverse("v1:tenant-review-queue-list", kwargs={"tenant_id": self.owner_tenant.id}),
        ]

        for endpoint in list_endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_authenticated_nested_detail_endpoints_smoke(self):
        detail_endpoints = [
            reverse(
                "v1:tenant-config-detail",
                kwargs={"tenant_id": self.owner_tenant.id, "pk": self.owner_config.id},
            ),
            reverse(
                "v1:tenant-entity-detail",
                kwargs={"tenant_id": self.owner_tenant.id, "pk": self.owner_entity.id},
            ),
            reverse(
                "v1:tenant-content-detail",
                kwargs={"tenant_id": self.owner_tenant.id, "pk": self.owner_content.id},
            ),
            reverse(
                "v1:tenant-skill-result-detail",
                kwargs={"tenant_id": self.owner_tenant.id, "pk": self.owner_skill_result.id},
            ),
            reverse(
                "v1:tenant-ingestion-run-detail",
                kwargs={"tenant_id": self.owner_tenant.id, "pk": self.owner_ingestion_run.id},
            ),
            reverse(
                "v1:tenant-source-config-detail",
                kwargs={"tenant_id": self.owner_tenant.id, "pk": self.owner_source_config.id},
            ),
            reverse(
                "v1:tenant-review-queue-detail",
                kwargs={"tenant_id": self.owner_tenant.id, "pk": self.owner_review_queue.id},
            ),
        ]

        feedback = UserFeedback.objects.create(
            tenant=self.owner_tenant,
            content=self.owner_content,
            user=self.owner,
            feedback_type=FeedbackType.UPVOTE,
        )
        detail_endpoints.append(
            reverse(
                "v1:tenant-feedback-detail",
                kwargs={"tenant_id": self.owner_tenant.id, "pk": feedback.id},
            )
        )

        for endpoint in detail_endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_source_config_create_validates_plugin_config(self):
        response = self.client.post(
            reverse("v1:tenant-source-config-list", kwargs={"tenant_id": self.owner_tenant.id}),
            {"plugin_name": SourcePluginName.RSS, "config": {}},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("config", response.json())


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


class EmbeddingIntegrationTests(TestCase):
    def setUp(self):
        embeddings.get_embedding_provider.cache_clear()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="embed-owner", password="testpass123")
        self.tenant = Tenant.objects.create(name="Embedding Tenant", user=self.user, topic_description="Infra")
        self.content = Content.objects.create(
            tenant=self.tenant,
            url="https://example.com/embed",
            title="Embedding Content",
            author="Author",
            source_plugin=SourcePluginName.RSS,
            published_date="2026-04-20T12:00:00Z",
            content_text="This article covers platform engineering practices.",
        )

    def tearDown(self):
        embeddings.get_embedding_provider.cache_clear()

    @patch("core.embeddings.get_embedding_provider")
    @patch("core.embeddings.get_qdrant_client")
    def test_upsert_content_embedding_persists_embedding_id_and_payload(self, client_mock, provider_mock):
        provider_mock.return_value.embed_text.return_value = [0.1, 0.2, 0.3]
        provider_mock.return_value.get_embedding_dimension.return_value = 3
        client_mock.return_value.get_collection.side_effect = RuntimeError("missing")

        embedding_id = upsert_content_embedding(self.content)

        self.content.refresh_from_db()
        self.assertEqual(self.content.embedding_id, embedding_id)
        client_mock.return_value.create_collection.assert_called_once()
        client_mock.return_value.upsert.assert_called_once()
        upsert_points = client_mock.return_value.upsert.call_args.kwargs["points"]
        self.assertEqual(upsert_points[0].payload["content_id"], self.content.id)
        self.assertFalse(upsert_points[0].payload["is_reference"])

    @patch("core.embeddings.get_qdrant_client")
    def test_search_similar_returns_qdrant_results_for_tenant_collection(self, client_mock):
        scored_point = SimpleNamespace(score=0.91, payload={"content_id": self.content.id})
        client_mock.return_value.get_collection.return_value = SimpleNamespace()
        client_mock.return_value.search.return_value = [scored_point]

        results = search_similar(self.tenant.id, [0.1, 0.2, 0.3], limit=3, exclude_content_id=self.content.id)

        self.assertEqual(results, [scored_point])
        client_mock.return_value.search.assert_called_once()

    @patch("core.embeddings.embed_text", return_value=[0.3, 0.2, 0.1])
    @patch("core.embeddings.search_similar", return_value=[SimpleNamespace(score=0.88, payload={"content_id": 999})])
    def test_search_similar_content_embeds_current_content_and_excludes_self(self, search_similar_mock, embed_text_mock):
        results = search_similar_content(self.content, limit=4, is_reference=False)

        self.assertEqual(len(results), 1)
        embed_text_mock.assert_called_once_with("Embedding Content\n\nThis article covers platform engineering practices.")
        search_similar_mock.assert_called_once_with(
            self.tenant.id,
            [0.3, 0.2, 0.1],
            limit=4,
            is_reference=False,
            exclude_content_id=self.content.id,
        )

    @patch("core.embeddings.search_similar")
    def test_get_reference_similarity_averages_reference_scores(self, search_mock):
        search_mock.return_value = [SimpleNamespace(score=0.8), SimpleNamespace(score=0.6)]

        similarity = get_reference_similarity(self.tenant.id, [0.1, 0.2, 0.3])

        self.assertEqual(similarity, 0.7)

    def test_get_reference_similarity_returns_zero_when_no_reference_matches(self):
        similarity = get_reference_similarity(self.tenant.id, [0.1, 0.2, 0.3])

        self.assertEqual(similarity, 0.0)

    @override_settings(EMBEDDING_PROVIDER="sentence-transformers")
    @patch("core.embeddings.SentenceTransformer")
    def test_get_embedding_provider_uses_sentence_transformer_backend(self, sentence_transformer_mock):
        provider = get_embedding_provider()

        self.assertEqual(provider.__class__.__name__, "SentenceTransformerEmbeddingProvider")
        sentence_transformer_mock.assert_called_once()

    @override_settings(EMBEDDING_PROVIDER="ollama")
    def test_get_embedding_provider_uses_ollama_backend(self):
        provider = get_embedding_provider()

        self.assertEqual(provider.__class__.__name__, "OllamaEmbeddingProvider")

    @override_settings(EMBEDDING_PROVIDER="openrouter")
    def test_get_embedding_provider_uses_openrouter_backend(self):
        provider = get_embedding_provider()

        self.assertEqual(provider.__class__.__name__, "OpenRouterEmbeddingProvider")

    @override_settings(EMBEDDING_PROVIDER="ollama", EMBEDDING_MODEL="nomic-embed-text", OLLAMA_URL="http://ollama:11434")
    @patch("core.embeddings.httpx.post")
    def test_ollama_embedding_provider_calls_embed_endpoint(self, post_mock):
        post_mock.return_value = SimpleNamespace(status_code=200, json=lambda: {"embeddings": [[0.3, 0.4]]}, raise_for_status=lambda: None)

        vector = embeddings.embed_text("ollama text")

        self.assertEqual(vector, [0.3, 0.4])
        self.assertIn("/api/embed", post_mock.call_args.args[0])

    @override_settings(
        EMBEDDING_PROVIDER="openrouter",
        EMBEDDING_MODEL="openai/text-embedding-3-small",
        OPENROUTER_API_KEY="test-key",
        OPENROUTER_API_BASE="https://openrouter.ai/api/v1",
        OPENROUTER_APP_NAME="newsletter-maker",
    )
    @patch("core.embeddings.httpx.post")
    def test_openrouter_embedding_provider_calls_embeddings_endpoint(self, post_mock):
        post_mock.return_value = SimpleNamespace(
            json=lambda: {"data": [{"embedding": [0.5, 0.6]}]},
            raise_for_status=lambda: None,
        )

        vector = embeddings.embed_text("api text")

        self.assertEqual(vector, [0.5, 0.6])
        self.assertIn("/embeddings", post_mock.call_args.args[0])
        self.assertEqual(post_mock.call_args.kwargs["headers"]["Authorization"], "Bearer test-key")

    @patch("core.management.commands.embedding_smoke.embed_text", return_value=[0.1, 0.2, 0.3])
    def test_embedding_smoke_command_prints_dimension(self, embed_text_mock):
        with patch("sys.stdout") as stdout_mock:
            call_command("embedding_smoke", text="test text")

        embed_text_mock.assert_called_once_with("test text")
        written_output = "".join(call.args[0] for call in stdout_mock.write.call_args_list if call.args)
        self.assertIn("Dimension: 3", written_output)

    @patch("core.management.commands.embedding_smoke.upsert_content_embedding", return_value="embedding-123")
    def test_embedding_smoke_command_can_upsert_content(self, upsert_mock):
        with patch("sys.stdout") as stdout_mock:
            call_command("embedding_smoke", content_id=self.content.id)

        upsert_mock.assert_called_once()
        written_output = "".join(call.args[0] for call in stdout_mock.write.call_args_list if call.args)
        self.assertIn("embedding-123", written_output)

    @patch("core.management.commands.seed_demo.upsert_content_embedding")
    def test_seed_demo_creates_reference_corpus_and_embeds_demo_content(self, upsert_mock):
        with patch("sys.stdout") as stdout_mock:
            call_command("seed_demo")

        tenant = Tenant.objects.get(name="Platform Engineering Weekly")
        self.assertTrue(Content.objects.filter(tenant=tenant, is_reference=True).exists())
        self.assertTrue(Content.objects.filter(tenant=tenant, is_reference=False).exists())
        self.assertEqual(upsert_mock.call_count, Content.objects.filter(tenant=tenant).count())
        written_output = "".join(call.args[0] for call in stdout_mock.write.call_args_list if call.args)
        self.assertIn("Reference corpus items", written_output)
