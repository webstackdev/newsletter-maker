from types import SimpleNamespace

import pytest
from django.contrib.auth.models import Group

from core.models import Content, Project, ReviewQueue, ReviewReason, SkillResult, SkillStatus
from core.pipeline import (
    CLASSIFICATION_SKILL_NAME,
    RELATED_CONTENT_SKILL_NAME,
    RELEVANCE_SKILL_NAME,
    SUMMARIZATION_SKILL_NAME,
    create_pending_skill_result,
    execute_ad_hoc_skill,
    execute_background_skill_result,
    run_content_classification,
    run_relevance_scoring,
    run_summarization,
)
from core.tasks import process_content

pytestmark = pytest.mark.django_db


@pytest.fixture
def pipeline_context(django_user_model):
    user = django_user_model.objects.create_user(username="pipeline-owner", password="testpass123")
    group = Group.objects.create(name="pipeline-team")
    user.groups.add(group)
    project = Project.objects.create(name="Pipeline Project", group=group, topic_description="Platform engineering")
    content = Content.objects.create(
        project=project,
        url="https://example.com/article",
        title="Kubernetes Release Notes",
        author="Editor",
        source_plugin="rss",
        published_date="2026-04-26T00:00:00Z",
        content_text="This article covers a new Kubernetes release and what changed for platform teams.",
        embedding_id="emb_123",
    )
    return SimpleNamespace(user=user, group=group, project=project, content=content)


def test_process_content_runs_full_pipeline_for_relevant_content(pipeline_context, mocker):
    mocker.patch(
        "core.pipeline.run_content_classification",
        return_value={
            "content_type": "release_notes",
            "confidence": 0.9,
            "explanation": "High confidence classification.",
            "model_used": "heuristic",
            "latency_ms": 0,
        },
    )
    mocker.patch(
        "core.pipeline.run_relevance_scoring",
        return_value={
            "relevance_score": 0.92,
            "explanation": "Very close to the project reference corpus.",
            "used_llm": False,
            "model_used": "embedding:test",
            "latency_ms": 0,
        },
    )
    mocker.patch(
        "core.pipeline.run_summarization",
        return_value={
            "summary": "A concise summary for the editor.",
            "model_used": "heuristic",
            "latency_ms": 0,
        },
    )

    result = process_content(pipeline_context.content.id)

    pipeline_context.content.refresh_from_db()
    assert result["status"] == "completed"
    assert pipeline_context.content.content_type == "release_notes"
    assert pipeline_context.content.relevance_score == pytest.approx(0.92)
    assert pipeline_context.content.is_active is True
    assert SkillResult.objects.filter(content=pipeline_context.content, skill_name=CLASSIFICATION_SKILL_NAME).count() == 1
    assert SkillResult.objects.filter(content=pipeline_context.content, skill_name=RELEVANCE_SKILL_NAME).count() == 1
    assert SkillResult.objects.filter(content=pipeline_context.content, skill_name=SUMMARIZATION_SKILL_NAME).count() == 1
    assert ReviewQueue.objects.filter(content=pipeline_context.content).count() == 0


def test_process_content_queues_borderline_items_for_review(pipeline_context, mocker):
    mocker.patch(
        "core.pipeline.run_content_classification",
        return_value={
            "content_type": "technical_article",
            "confidence": 0.9,
            "explanation": "High confidence classification.",
            "model_used": "heuristic",
            "latency_ms": 0,
        },
    )
    mocker.patch(
        "core.pipeline.run_relevance_scoring",
        return_value={
            "relevance_score": 0.55,
            "explanation": "Borderline similarity to the project baseline.",
            "used_llm": False,
            "model_used": "embedding:test",
            "latency_ms": 0,
        },
    )
    summarize_mock = mocker.patch("core.pipeline.run_summarization")

    result = process_content(pipeline_context.content.id)

    pipeline_context.content.refresh_from_db()
    assert result["status"] == "review"
    assert pipeline_context.content.is_active is True
    summarize_mock.assert_not_called()
    review_item = ReviewQueue.objects.get(content=pipeline_context.content, reason=ReviewReason.BORDERLINE_RELEVANCE)
    assert review_item.confidence == pytest.approx(0.55)


def test_process_content_archives_irrelevant_items(pipeline_context, mocker):
    mocker.patch(
        "core.pipeline.run_content_classification",
        return_value={
            "content_type": "other",
            "confidence": 0.7,
            "explanation": "Low signal classification.",
            "model_used": "heuristic",
            "latency_ms": 0,
        },
    )
    mocker.patch(
        "core.pipeline.run_relevance_scoring",
        return_value={
            "relevance_score": 0.2,
            "explanation": "Far from the project reference corpus.",
            "used_llm": False,
            "model_used": "embedding:test",
            "latency_ms": 0,
        },
    )
    summarize_mock = mocker.patch("core.pipeline.run_summarization")

    result = process_content(pipeline_context.content.id)

    pipeline_context.content.refresh_from_db()
    assert result["status"] == "archived"
    assert pipeline_context.content.is_active is False
    summarize_mock.assert_not_called()
    assert ReviewQueue.objects.filter(content=pipeline_context.content, reason=ReviewReason.BORDERLINE_RELEVANCE).count() == 0


def test_process_content_adds_review_item_for_low_confidence_classification(pipeline_context, mocker):
    mocker.patch(
        "core.pipeline.run_content_classification",
        return_value={
            "content_type": "other",
            "confidence": 0.3,
            "explanation": "Ambiguous content.",
            "model_used": "heuristic",
            "latency_ms": 0,
        },
    )
    mocker.patch(
        "core.pipeline.run_relevance_scoring",
        return_value={
            "relevance_score": 0.9,
            "explanation": "Close to the project baseline.",
            "used_llm": False,
            "model_used": "embedding:test",
            "latency_ms": 0,
        },
    )
    mocker.patch(
        "core.pipeline.run_summarization",
        return_value={
            "summary": "Summary present even though classification confidence was low.",
            "model_used": "heuristic",
            "latency_ms": 0,
        },
    )

    result = process_content(pipeline_context.content.id)

    assert result["status"] == "completed"
    review_item = ReviewQueue.objects.get(
        content=pipeline_context.content,
        reason=ReviewReason.LOW_CONFIDENCE_CLASSIFICATION,
    )
    assert review_item.confidence == pytest.approx(0.3)


def test_run_content_classification_uses_openrouter_response_and_normalizes_values(
    pipeline_context,
    settings,
    mocker,
):
    settings.OPENROUTER_API_KEY = "test-key"
    mocker.patch(
        "core.pipeline.openrouter_chat_json",
        return_value=SimpleNamespace(
            payload={
                "content_type": "unexpected_type",
                "confidence": "1.7",
                "explanation": "Model decided this was novel.",
            },
            model="openrouter/test-model",
            latency_ms=123,
        ),
    )

    result = run_content_classification(pipeline_context.content)

    assert result == {
        "content_type": "other",
        "confidence": 1.0,
        "explanation": "Model decided this was novel.",
        "model_used": "openrouter/test-model",
        "latency_ms": 123,
    }


def test_run_relevance_scoring_uses_openrouter_for_borderline_similarity(
    pipeline_context,
    settings,
    mocker,
):
    settings.OPENROUTER_API_KEY = "test-key"
    mocker.patch("core.pipeline.build_content_embedding_text", return_value="embedding text")
    mocker.patch("core.pipeline.embed_text", return_value=[0.1, 0.2, 0.3])
    mocker.patch("core.pipeline.get_reference_similarity", return_value=0.6)
    openrouter_mock = mocker.patch(
        "core.pipeline.openrouter_chat_json",
        return_value=SimpleNamespace(
            payload={
                "relevance_score": "0.74",
                "explanation": "LLM confirmed the borderline match.",
            },
            model="openrouter/relevance-model",
            latency_ms=87,
        ),
    )

    result = run_relevance_scoring(pipeline_context.content)

    assert result == {
        "relevance_score": 0.74,
        "explanation": "LLM confirmed the borderline match.",
        "used_llm": True,
        "model_used": "openrouter/relevance-model",
        "latency_ms": 87,
    }
    openrouter_mock.assert_called_once()


def test_run_summarization_falls_back_to_heuristic_when_openrouter_fails(
    pipeline_context,
    settings,
    mocker,
):
    settings.OPENROUTER_API_KEY = "test-key"
    mocker.patch("core.pipeline.openrouter_chat_json", side_effect=RuntimeError("model unavailable"))

    result = run_summarization(pipeline_context.content)

    assert result["model_used"] == "heuristic"
    assert result["latency_ms"] == 0
    assert result["summary"] == (
        "This article covers a new Kubernetes release and what changed for platform teams."
    )


def test_execute_ad_hoc_classification_supersedes_previous_result_and_updates_review_item(
    pipeline_context,
    mocker,
):
    classification_mock = mocker.patch(
        "core.pipeline.run_content_classification",
        side_effect=[
            {
                "content_type": "other",
                "confidence": 0.3,
                "explanation": "Very ambiguous.",
                "model_used": "heuristic",
                "latency_ms": 0,
            },
            {
                "content_type": "tutorial",
                "confidence": 0.45,
                "explanation": "Still low confidence, but improved.",
                "model_used": "heuristic",
                "latency_ms": 0,
            },
        ],
    )

    first_result = execute_ad_hoc_skill(pipeline_context.content, CLASSIFICATION_SKILL_NAME)
    second_result = execute_ad_hoc_skill(pipeline_context.content, CLASSIFICATION_SKILL_NAME)

    first_result.refresh_from_db()
    pipeline_context.content.refresh_from_db()
    review_item = ReviewQueue.objects.get(
        content=pipeline_context.content,
        reason=ReviewReason.LOW_CONFIDENCE_CLASSIFICATION,
        resolved=False,
    )

    assert classification_mock.call_count == 2
    assert first_result.status == SkillStatus.COMPLETED
    assert second_result.status == SkillStatus.COMPLETED
    assert first_result.superseded_by_id == second_result.id
    assert pipeline_context.content.content_type == "tutorial"
    assert review_item.confidence == pytest.approx(0.45)
    assert ReviewQueue.objects.filter(
        content=pipeline_context.content,
        reason=ReviewReason.LOW_CONFIDENCE_CLASSIFICATION,
    ).count() == 1


def test_execute_ad_hoc_relevance_creates_review_item_for_borderline_scores(
    pipeline_context,
    mocker,
):
    mocker.patch(
        "core.pipeline.run_relevance_scoring",
        return_value={
            "relevance_score": 0.55,
            "explanation": "Borderline relevance for manual review.",
            "used_llm": False,
            "model_used": "embedding:test",
            "latency_ms": 0,
        },
    )

    result = execute_ad_hoc_skill(pipeline_context.content, RELEVANCE_SKILL_NAME)

    pipeline_context.content.refresh_from_db()
    review_item = ReviewQueue.objects.get(
        content=pipeline_context.content,
        reason=ReviewReason.BORDERLINE_RELEVANCE,
        resolved=False,
    )

    assert result.status == SkillStatus.COMPLETED
    assert result.confidence == pytest.approx(0.55)
    assert pipeline_context.content.relevance_score == pytest.approx(0.55)
    assert pipeline_context.content.is_active is True
    assert review_item.confidence == pytest.approx(0.55)


def test_execute_ad_hoc_summarization_returns_failed_result_when_relevance_is_too_low(
    pipeline_context,
):
    pipeline_context.content.relevance_score = 0.2
    pipeline_context.content.save(update_fields=["relevance_score"])

    result = execute_ad_hoc_skill(pipeline_context.content, SUMMARIZATION_SKILL_NAME)

    assert result.status == SkillStatus.FAILED
    assert "Summarization requires relevance_score" in result.error_message


def test_execute_ad_hoc_related_content_returns_failed_result_on_search_error(
    pipeline_context,
    mocker,
):
    mocker.patch("core.pipeline.search_similar_content", side_effect=RuntimeError("vector index unavailable"))

    result = execute_ad_hoc_skill(pipeline_context.content, RELATED_CONTENT_SKILL_NAME)

    assert result.status == SkillStatus.FAILED
    assert result.skill_name == RELATED_CONTENT_SKILL_NAME
    assert result.error_message == "vector index unavailable"


def test_create_pending_skill_result_rejects_non_async_skill(pipeline_context):
    with pytest.raises(ValueError, match="Unsupported async skill name"):
        create_pending_skill_result(pipeline_context.content, CLASSIFICATION_SKILL_NAME)


def test_execute_background_skill_result_rejects_skill_name_mismatch(pipeline_context):
    pending_result = create_pending_skill_result(pipeline_context.content, RELEVANCE_SKILL_NAME)

    with pytest.raises(ValueError, match="is for relevance_scoring, not summarization"):
        execute_background_skill_result(pending_result.id, SUMMARIZATION_SKILL_NAME)


def test_execute_background_skill_result_completes_summary_when_requirements_are_met(
    pipeline_context,
    mocker,
):
    pipeline_context.content.relevance_score = 0.9
    pipeline_context.content.save(update_fields=["relevance_score"])
    pending_result = create_pending_skill_result(pipeline_context.content, SUMMARIZATION_SKILL_NAME)
    mocker.patch(
        "core.pipeline.run_summarization",
        return_value={
            "summary": "Manual summary output.",
            "model_used": "heuristic",
            "latency_ms": 0,
        },
    )

    result = execute_background_skill_result(pending_result.id, SUMMARIZATION_SKILL_NAME)

    pending_result.refresh_from_db()
    assert result.status == SkillStatus.COMPLETED
    assert pending_result.status == SkillStatus.COMPLETED
    assert pending_result.result_data == {"summary": "Manual summary output.", "model_used": "heuristic", "latency_ms": 0}

