from types import SimpleNamespace

from django.core.management import call_command
import pytest

from core import embeddings
from core.embeddings import get_embedding_provider, get_reference_similarity, search_similar, search_similar_content, upsert_content_embedding
from core.models import Content, SourcePluginName, Tenant


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_embedding_provider_cache():
    embeddings.get_embedding_provider.cache_clear()
    yield
    embeddings.get_embedding_provider.cache_clear()


@pytest.fixture
def embedding_context(django_user_model):
    user = django_user_model.objects.create_user(username="embed-owner", password="testpass123")
    tenant = Tenant.objects.create(name="Embedding Tenant", user=user, topic_description="Infra")
    content = Content.objects.create(
        tenant=tenant,
        url="https://example.com/embed",
        title="Embedding Content",
        author="Author",
        source_plugin=SourcePluginName.RSS,
        published_date="2026-04-20T12:00:00Z",
        content_text="This article covers platform engineering practices.",
    )
    return SimpleNamespace(user=user, tenant=tenant, content=content)


def test_upsert_content_embedding_persists_embedding_id_and_payload(embedding_context, mocker):
    provider_mock = mocker.patch("core.embeddings.get_embedding_provider")
    client_mock = mocker.patch("core.embeddings.get_qdrant_client")
    provider_mock.return_value.embed_text.return_value = [0.1, 0.2, 0.3]
    provider_mock.return_value.get_embedding_dimension.return_value = 3
    client_mock.return_value.get_collection.side_effect = RuntimeError("missing")

    embedding_id = upsert_content_embedding(embedding_context.content)

    embedding_context.content.refresh_from_db()
    assert embedding_context.content.embedding_id == embedding_id
    client_mock.return_value.create_collection.assert_called_once()
    client_mock.return_value.upsert.assert_called_once()
    upsert_points = client_mock.return_value.upsert.call_args.kwargs["points"]
    assert upsert_points[0].payload["content_id"] == embedding_context.content.id
    assert upsert_points[0].payload["is_reference"] is False

def test_search_similar_returns_qdrant_results_for_tenant_collection(embedding_context, mocker):
    client_mock = mocker.patch("core.embeddings.get_qdrant_client")
    scored_point = SimpleNamespace(score=0.91, payload={"content_id": embedding_context.content.id})
    client_mock.return_value.get_collection.return_value = SimpleNamespace()
    client_mock.return_value.search.return_value = [scored_point]

    results = search_similar(embedding_context.tenant.id, [0.1, 0.2, 0.3], limit=3, exclude_content_id=embedding_context.content.id)

    assert results == [scored_point]
    client_mock.return_value.search.assert_called_once()

def test_search_similar_content_embeds_current_content_and_excludes_self(embedding_context, mocker):
    embed_text_mock = mocker.patch("core.embeddings.embed_text", return_value=[0.3, 0.2, 0.1])
    search_similar_mock = mocker.patch(
        "core.embeddings.search_similar",
        return_value=[SimpleNamespace(score=0.88, payload={"content_id": 999})],
    )

    results = search_similar_content(embedding_context.content, limit=4, is_reference=False)

    assert len(results) == 1
    embed_text_mock.assert_called_once_with("Embedding Content\n\nThis article covers platform engineering practices.")
    search_similar_mock.assert_called_once_with(
        embedding_context.tenant.id,
        [0.3, 0.2, 0.1],
        limit=4,
        is_reference=False,
        exclude_content_id=embedding_context.content.id,
    )

def test_get_reference_similarity_averages_reference_scores(embedding_context, mocker):
    search_mock = mocker.patch("core.embeddings.search_similar")
    search_mock.return_value = [SimpleNamespace(score=0.8), SimpleNamespace(score=0.6)]

    similarity = get_reference_similarity(embedding_context.tenant.id, [0.1, 0.2, 0.3])

    assert similarity == 0.7

def test_get_reference_similarity_returns_zero_when_no_reference_matches(embedding_context):
    similarity = get_reference_similarity(embedding_context.tenant.id, [0.1, 0.2, 0.3])

    assert similarity == 0.0

def test_get_embedding_provider_uses_sentence_transformer_backend(settings, mocker):
    settings.EMBEDDING_PROVIDER = "sentence-transformers"
    sentence_transformer_mock = mocker.patch("core.embeddings.SentenceTransformer")

    provider = get_embedding_provider()

    assert provider.__class__.__name__ == "SentenceTransformerEmbeddingProvider"
    sentence_transformer_mock.assert_called_once()

def test_get_embedding_provider_uses_ollama_backend(settings):
    settings.EMBEDDING_PROVIDER = "ollama"

    provider = get_embedding_provider()

    assert provider.__class__.__name__ == "OllamaEmbeddingProvider"

def test_get_embedding_provider_uses_openrouter_backend(settings):
    settings.EMBEDDING_PROVIDER = "openrouter"

    provider = get_embedding_provider()

    assert provider.__class__.__name__ == "OpenRouterEmbeddingProvider"

def test_ollama_embedding_provider_calls_embed_endpoint(settings, mocker):
    settings.EMBEDDING_PROVIDER = "ollama"
    settings.EMBEDDING_MODEL = "nomic-embed-text"
    settings.OLLAMA_URL = "http://ollama:11434"
    post_mock = mocker.patch("core.embeddings.httpx.post")
    post_mock.return_value = SimpleNamespace(status_code=200, json=lambda: {"embeddings": [[0.3, 0.4]]}, raise_for_status=lambda: None)

    vector = embeddings.embed_text("ollama text")

    assert vector == [0.3, 0.4]
    assert "/api/embed" in post_mock.call_args.args[0]

def test_openrouter_embedding_provider_calls_embeddings_endpoint(settings, mocker):
    settings.EMBEDDING_PROVIDER = "openrouter"
    settings.EMBEDDING_MODEL = "openai/text-embedding-3-small"
    settings.OPENROUTER_API_KEY = "test-key"
    settings.OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
    settings.OPENROUTER_APP_NAME = "newsletter-maker"
    post_mock = mocker.patch("core.embeddings.httpx.post")
    post_mock.return_value = SimpleNamespace(
        json=lambda: {"data": [{"embedding": [0.5, 0.6]}]},
        raise_for_status=lambda: None,
    )

    vector = embeddings.embed_text("api text")

    assert vector == [0.5, 0.6]
    assert "/embeddings" in post_mock.call_args.args[0]
    assert post_mock.call_args.kwargs["headers"]["Authorization"] == "Bearer test-key"


def test_embedding_smoke_command_prints_dimension(mocker, capsys):
    embed_text_mock = mocker.patch("core.management.commands.embedding_smoke.embed_text", return_value=[0.1, 0.2, 0.3])

    call_command("embedding_smoke", text="test text")

    embed_text_mock.assert_called_once_with("test text")
    assert "Dimension: 3" in capsys.readouterr().out


def test_embedding_smoke_command_can_upsert_content(embedding_context, mocker, capsys):
    upsert_mock = mocker.patch("core.management.commands.embedding_smoke.upsert_content_embedding", return_value="embedding-123")

    call_command("embedding_smoke", content_id=embedding_context.content.id)

    upsert_mock.assert_called_once()
    assert "embedding-123" in capsys.readouterr().out


def test_seed_demo_creates_reference_corpus_and_embeds_demo_content(mocker, capsys):
    upsert_mock = mocker.patch("core.management.commands.seed_demo.upsert_content_embedding")

    call_command("seed_demo")

    tenant = Tenant.objects.get(name="Platform Engineering Weekly")
    assert Content.objects.filter(tenant=tenant, is_reference=True).exists()
    assert Content.objects.filter(tenant=tenant, is_reference=False).exists()
    assert upsert_mock.call_count == Content.objects.filter(tenant=tenant).count()
    assert "Reference corpus items" in capsys.readouterr().out
