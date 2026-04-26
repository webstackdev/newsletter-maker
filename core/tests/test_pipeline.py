from types import SimpleNamespace

import pytest

from core.models import Content, ReviewQueue, ReviewReason, SkillResult, Tenant
from core.pipeline import CLASSIFICATION_SKILL_NAME, RELEVANCE_SKILL_NAME, SUMMARIZATION_SKILL_NAME
from core.tasks import process_content

pytestmark = pytest.mark.django_db


@pytest.fixture
def pipeline_context(django_user_model):
    user = django_user_model.objects.create_user(username="pipeline-owner", password="testpass123")
    tenant = Tenant.objects.create(name="Pipeline Tenant", user=user, topic_description="Platform engineering")
    content = Content.objects.create(
        tenant=tenant,
        url="https://example.com/article",
        title="Kubernetes Release Notes",
        author="Editor",
        source_plugin="rss",
        published_date="2026-04-26T00:00:00Z",
        content_text="This article covers a new Kubernetes release and what changed for platform teams.",
        embedding_id="emb_123",
    )
    return SimpleNamespace(user=user, tenant=tenant, content=content)


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
            "explanation": "Very close to the tenant reference corpus.",
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
            "explanation": "Borderline similarity to the tenant baseline.",
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
            "explanation": "Far from the tenant reference corpus.",
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
            "explanation": "Close to the tenant baseline.",
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