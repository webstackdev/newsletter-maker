from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from core import embeddings
from core.embeddings import get_embedding_provider, get_reference_similarity, search_similar, search_similar_content, upsert_content_embedding
from core.models import Content, SourcePluginName, Tenant


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
