from types import SimpleNamespace
from io import StringIO
from unittest.mock import call

import httpx
import pytest
from django.contrib.auth.models import Group
from django.core.management import CommandError, call_command
from qdrant_client.http.exceptions import ResponseHandlingException

from core import embeddings
from core.embeddings import (
    build_content_embedding_text,
    build_search_filter,
    get_embedding_provider,
    get_reference_similarity,
    normalize_text,
    search_similar,
    search_similar_content,
    serialize_published_date,
    upsert_content_embedding,
)
from core.models import (
    Content,
    Entity,
    IngestionRun,
    Project,
    ReviewQueue,
    SkillResult,
    SourceConfig,
    SourcePluginName,
    UserFeedback,
)
from core.pipeline import (
    CLASSIFICATION_SKILL_NAME,
    RELEVANCE_SKILL_NAME,
    SUMMARIZATION_SKILL_NAME,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_embedding_provider_cache():
    embeddings.get_embedding_provider.cache_clear()
    yield
    embeddings.get_embedding_provider.cache_clear()


@pytest.fixture
def embedding_context(django_user_model):
    user = django_user_model.objects.create_user(username="embed-owner", password="testpass123")
    group = Group.objects.create(name="embedding-team")
    user.groups.add(group)
    project = Project.objects.create(name="Embedding Project", group=group, topic_description="Infra")
    content = Content.objects.create(
        project=project,
        url="https://example.com/embed",
        title="Embedding Content",
        author="Author",
        source_plugin=SourcePluginName.RSS,
        published_date="2026-04-20T12:00:00Z",
        content_text="This article covers platform engineering practices.",
    )
    return SimpleNamespace(user=user, group=group, project=project, content=content)


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

def test_search_similar_returns_qdrant_results_for_project_collection(embedding_context, mocker):
    client_mock = mocker.patch("core.embeddings.get_qdrant_client")
    scored_point = SimpleNamespace(score=0.91, payload={"content_id": embedding_context.content.id})
    client_mock.return_value.get_collection.return_value = SimpleNamespace()
    client_mock.return_value.search.return_value = [scored_point]

    results = search_similar(embedding_context.project.id, [0.1, 0.2, 0.3], limit=3, exclude_content_id=embedding_context.content.id)

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
        embedding_context.project.id,
        [0.3, 0.2, 0.1],
        limit=4,
        is_reference=False,
        exclude_content_id=embedding_context.content.id,
    )

def test_get_reference_similarity_averages_reference_scores(embedding_context, mocker):
    search_mock = mocker.patch("core.embeddings.search_similar")
    search_mock.return_value = [SimpleNamespace(score=0.8), SimpleNamespace(score=0.6)]

    similarity = get_reference_similarity(embedding_context.project.id, [0.1, 0.2, 0.3])

    assert similarity == 0.7

def test_get_reference_similarity_returns_zero_when_no_reference_matches(embedding_context):
    similarity = get_reference_similarity(embedding_context.project.id, [0.1, 0.2, 0.3])

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
    post_mock = mocker.patch("core.embeddings.httpx.post")
    post_mock.return_value = SimpleNamespace(status_code=200, json=lambda: {"embeddings": [[0.3, 0.4]]}, raise_for_status=lambda: None)

    vector = embeddings.embed_text("ollama text")

    assert vector == [0.3, 0.4]
    assert "/api/embed" in post_mock.call_args.args[0]

def test_openrouter_embedding_provider_calls_embeddings_endpoint(settings, mocker):
    settings.EMBEDDING_PROVIDER = "openrouter"
    settings.EMBEDDING_MODEL = "openai/text-embedding-3-small"
    post_mock = mocker.patch("core.embeddings.httpx.post")
    post_mock.return_value = SimpleNamespace(
        json=lambda: {"data": [{"embedding": [0.5, 0.6]}]},
        raise_for_status=lambda: None,
    )

    vector = embeddings.embed_text("api text")

    assert vector == [0.5, 0.6]
    assert "/embeddings" in post_mock.call_args.args[0]
    assert post_mock.call_args.kwargs["headers"]["Authorization"] == "Bearer test-key"


def test_openrouter_embedding_provider_requires_api_key(settings):
    settings.EMBEDDING_PROVIDER = "openrouter"
    settings.OPENROUTER_API_KEY = ""

    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY must be set"):
        embeddings.embed_text("api text")


def test_ollama_embedding_provider_falls_back_to_legacy_endpoint_on_404(settings, mocker):
    settings.EMBEDDING_PROVIDER = "ollama"
    settings.EMBEDDING_MODEL = "nomic-embed-text"
    embed_response = SimpleNamespace(status_code=404)
    legacy_response = SimpleNamespace(
        json=lambda: {"embedding": [0.9, 0.8]},
        raise_for_status=lambda: None,
    )
    post_mock = mocker.patch("core.embeddings.httpx.post", side_effect=[embed_response, legacy_response])

    vector = embeddings.embed_text("legacy text")

    assert vector == [0.9, 0.8]
    assert post_mock.call_args_list[1].args[0].endswith("/api/embeddings")


def test_get_embedding_provider_rejects_unsupported_backend(settings):
    settings.EMBEDDING_PROVIDER = "unsupported"

    with pytest.raises(ValueError, match="Unsupported embedding provider"):
        get_embedding_provider()


def test_ensure_project_collection_skips_create_when_collection_exists(embedding_context, mocker):
    client_mock = mocker.patch("core.embeddings.get_qdrant_client")
    exists_mock = mocker.patch("core.embeddings.project_collection_exists", return_value=True)

    embeddings.ensure_project_collection(embedding_context.project.id)

    exists_mock.assert_called_once_with(embedding_context.project.id)
    client_mock.return_value.create_collection.assert_not_called()


def test_project_collection_exists_returns_false_when_lookup_raises(embedding_context, mocker):
    client_mock = mocker.patch("core.embeddings.get_qdrant_client")
    client_mock.return_value.get_collection.side_effect = RuntimeError("missing")

    assert embeddings.project_collection_exists(embedding_context.project.id) is False


def test_build_content_embedding_text_skips_blank_parts(embedding_context):
    embedding_context.content.title = ""

    assert build_content_embedding_text(embedding_context.content) == "This article covers platform engineering practices."


@pytest.mark.parametrize(
    ("raw_text", "expected"),
    [
        ("  trimmed  ", "trimmed"),
        ("   ", "empty content"),
    ],
)
def test_normalize_text_handles_blank_and_trimmed_input(raw_text, expected):
    assert normalize_text(raw_text) == expected


def test_serialize_published_date_handles_string_and_fallback_values():
    assert serialize_published_date("2026-04-20T12:00:00Z") == "2026-04-20T12:00:00+00:00"
    assert serialize_published_date("not-a-date") == "not-a-date"
    assert serialize_published_date(123) == "123"


def test_build_search_filter_returns_none_without_conditions():
    assert build_search_filter() is None


def test_build_search_filter_supports_reference_and_exclusion_conditions():
    filter_value = build_search_filter(is_reference=True, exclude_content_id=42)

    assert filter_value.must[0].key == "is_reference"
    assert filter_value.must[0].match.value is True
    assert filter_value.must_not[0].key == "content_id"
    assert filter_value.must_not[0].match.value == 42


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

    project = Project.objects.get(name="Platform Engineering Weekly")
    assert Entity.objects.filter(project=project).count() == 15
    assert SourceConfig.objects.filter(project=project).count() == 8
    assert Content.objects.filter(project=project, is_reference=True).count() == 50
    assert Content.objects.filter(project=project, is_reference=False).count() == 200
    assert SkillResult.objects.filter(project=project, skill_name=CLASSIFICATION_SKILL_NAME).count() == 200
    assert SkillResult.objects.filter(project=project, skill_name=RELEVANCE_SKILL_NAME).count() == 200
    assert SkillResult.objects.filter(project=project, skill_name=SUMMARIZATION_SKILL_NAME).count() == 115
    assert ReviewQueue.objects.filter(project=project).exists()
    assert UserFeedback.objects.filter(project=project).count() == 45
    assert IngestionRun.objects.filter(project=project).count() == 6
    assert upsert_mock.call_count == 250
    output = capsys.readouterr().out
    assert "Reference corpus items: 50" in output
    assert "Demo content items: 200" in output


def test_seed_demo_is_stable_on_rerun(mocker):
    mocker.patch("core.management.commands.seed_demo.upsert_content_embedding")

    call_command("seed_demo")
    call_command("seed_demo")

    project = Project.objects.get(name="Platform Engineering Weekly")
    assert Entity.objects.filter(project=project).count() == 15
    assert SourceConfig.objects.filter(project=project).count() == 8
    assert Content.objects.filter(project=project, is_reference=True).count() == 50
    assert Content.objects.filter(project=project, is_reference=False).count() == 200
    assert SkillResult.objects.filter(project=project).count() == 515
    assert ReviewQueue.objects.filter(project=project).count() > 0
    assert UserFeedback.objects.filter(project=project).count() == 45
    assert IngestionRun.objects.filter(project=project).count() == 6


def test_seed_demo_skips_embeddings_when_vector_stack_is_unavailable(mocker, capsys):
    upsert_mock = mocker.patch(
        "core.management.commands.seed_demo.upsert_content_embedding",
        side_effect=ResponseHandlingException(httpx.ConnectError("connection refused")),
    )

    call_command("seed_demo")

    project = Project.objects.get(name="Platform Engineering Weekly")
    assert Content.objects.filter(project=project, is_reference=True).count() == 50
    assert Content.objects.filter(project=project, is_reference=False).count() == 200
    assert SkillResult.objects.filter(project=project).count() == 515
    assert upsert_mock.call_count == 1
    combined_output = capsys.readouterr()
    assert "Skipping remaining embedding sync" in combined_output.err
    assert "Upserted embeddings for 0 seeded content item(s)." in combined_output.out


def test_sync_embeddings_scopes_to_requested_content_id(embedding_context, mocker):
    sibling_content = Content.objects.create(
        project=embedding_context.project,
        url="https://example.com/embed-sibling",
        title="Sibling Content",
        author="Author",
        source_plugin=SourcePluginName.RSS,
        published_date="2026-04-21T12:00:00Z",
        content_text="Sibling body.",
    )
    upsert_mock = mocker.patch("core.management.commands.sync_embeddings.upsert_content_embedding")
    stdout = StringIO()

    call_command("sync_embeddings", content_id=embedding_context.content.id, stdout=stdout)

    upsert_mock.assert_called_once_with(embedding_context.content)
    assert sibling_content.id != embedding_context.content.id
    assert "Synced embeddings for 1 content item(s)." in stdout.getvalue()


def test_sync_embeddings_filters_project_and_references_only(embedding_context, django_user_model, mocker):
    other_user = django_user_model.objects.create_user(username="embed-owner-2", password="testpass123")
    other_group = Group.objects.create(name="embedding-team-2")
    other_user.groups.add(other_group)
    other_project = Project.objects.create(name="Other Embedding Project", group=other_group, topic_description="Other")
    same_project_reference = Content.objects.create(
        project=embedding_context.project,
        url="https://example.com/reference-item",
        title="Reference Item",
        author="Author",
        source_plugin=SourcePluginName.RSS,
        published_date="2026-04-22T12:00:00Z",
        content_text="Reference body.",
        is_reference=True,
    )
    Content.objects.create(
        project=embedding_context.project,
        url="https://example.com/non-reference-item",
        title="Non Reference Item",
        author="Author",
        source_plugin=SourcePluginName.RSS,
        published_date="2026-04-23T12:00:00Z",
        content_text="Non reference body.",
        is_reference=False,
    )
    Content.objects.create(
        project=other_project,
        url="https://example.com/other-project-reference",
        title="Other Project Reference",
        author="Author",
        source_plugin=SourcePluginName.RSS,
        published_date="2026-04-24T12:00:00Z",
        content_text="Other project reference body.",
        is_reference=True,
    )
    upsert_mock = mocker.patch("core.management.commands.sync_embeddings.upsert_content_embedding")

    call_command(
        "sync_embeddings",
        project_id=embedding_context.project.id,
        references_only=True,
    )

    assert upsert_mock.call_args_list == [call(same_project_reference)]


def test_sync_embeddings_raises_command_error_when_scope_matches_no_content():
    with pytest.raises(CommandError, match="No content records matched the requested scope"):
        call_command("sync_embeddings", project_id=999999)
