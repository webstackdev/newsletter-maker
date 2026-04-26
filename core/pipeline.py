from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any, Literal, TypedDict

from django.conf import settings
from langgraph.graph import END, StateGraph

from core.embeddings import build_content_embedding_text, embed_text, get_reference_similarity, search_similar_content
from core.llm import openrouter_chat_json
from core.models import Content, ReviewQueue, ReviewReason, SkillResult, SkillStatus

logger = logging.getLogger(__name__)

CLASSIFICATION_SKILL_NAME = "content_classification"
RELEVANCE_SKILL_NAME = "relevance_scoring"
SUMMARIZATION_SKILL_NAME = "summarization"
RELATED_CONTENT_SKILL_NAME = "find_related"

CONTENT_TYPES = (
    "technical_article",
    "tutorial",
    "opinion",
    "product_announcement",
    "event",
    "release_notes",
    "other",
)


class PipelineState(TypedDict, total=False):
    content_id: int
    tenant_id: int
    classification: dict[str, Any] | None
    relevance: dict[str, Any] | None
    summary: dict[str, Any] | None
    status: str


@lru_cache(maxsize=1)
def get_ingestion_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("classify", classify_node)
    graph.add_node("score_relevance", relevance_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("archive", archive_node)
    graph.add_node("queue_review", queue_review_node)
    graph.set_entry_point("classify")
    graph.add_edge("classify", "score_relevance")
    graph.add_conditional_edges(
        "score_relevance",
        route_by_relevance,
        {
            "relevant": "summarize",
            "borderline": "queue_review",
            "irrelevant": "archive",
        },
    )
    graph.add_edge("summarize", END)
    graph.add_edge("archive", END)
    graph.add_edge("queue_review", END)
    return graph.compile()


def process_content_pipeline(content_id: int) -> PipelineState:
    content = Content.objects.select_related("tenant").get(pk=content_id)
    initial_state: PipelineState = {
        "content_id": content.id,
        "tenant_id": content.tenant_id,
        "status": "processing",
    }
    return get_ingestion_graph().invoke(initial_state)


def classify_node(state: PipelineState) -> PipelineState:
    content = _get_content(state)
    classification = _execute_with_retries(CLASSIFICATION_SKILL_NAME, lambda: run_content_classification(content))
    content.content_type = classification["content_type"]
    content.save(update_fields=["content_type"])
    _create_skill_result(
        content,
        skill_name=CLASSIFICATION_SKILL_NAME,
        status=SkillStatus.COMPLETED,
        result_data=classification,
        model_used=classification["model_used"],
        latency_ms=classification["latency_ms"],
        confidence=classification["confidence"],
    )
    if classification["confidence"] < settings.AI_CLASSIFICATION_REVIEW_THRESHOLD:
        _upsert_review_queue_item(
            content,
            reason=ReviewReason.LOW_CONFIDENCE_CLASSIFICATION,
            confidence=float(classification["confidence"]),
        )
    return {"classification": classification}


def relevance_node(state: PipelineState) -> PipelineState:
    content = _get_content(state)
    relevance = _execute_with_retries(RELEVANCE_SKILL_NAME, lambda: run_relevance_scoring(content))
    content.relevance_score = relevance["relevance_score"]
    content.is_active = True
    content.save(update_fields=["relevance_score", "is_active"])
    _create_skill_result(
        content,
        skill_name=RELEVANCE_SKILL_NAME,
        status=SkillStatus.COMPLETED,
        result_data=relevance,
        model_used=relevance["model_used"],
        latency_ms=relevance["latency_ms"],
        confidence=relevance["relevance_score"],
    )
    return {"relevance": relevance}


def summarize_node(state: PipelineState) -> PipelineState:
    content = _get_content(state)
    summary = _execute_with_retries(SUMMARIZATION_SKILL_NAME, lambda: run_summarization(content))
    _create_skill_result(
        content,
        skill_name=SUMMARIZATION_SKILL_NAME,
        status=SkillStatus.COMPLETED,
        result_data=summary,
        model_used=summary["model_used"],
        latency_ms=summary["latency_ms"],
    )
    return {"summary": summary, "status": "completed"}


def archive_node(state: PipelineState) -> PipelineState:
    content = _get_content(state)
    content.is_active = False
    content.save(update_fields=["is_active"])
    return {"status": "archived"}


def queue_review_node(state: PipelineState) -> PipelineState:
    content = _get_content(state)
    relevance = state.get("relevance") or {}
    _upsert_review_queue_item(
        content,
        reason=ReviewReason.BORDERLINE_RELEVANCE,
        confidence=float(relevance.get("relevance_score", settings.AI_RELEVANCE_REVIEW_THRESHOLD)),
    )
    content.is_active = True
    content.save(update_fields=["is_active"])
    return {"status": "review"}


def route_by_relevance(state: PipelineState) -> Literal["relevant", "borderline", "irrelevant"]:
    relevance = state.get("relevance") or {}
    score = float(relevance.get("relevance_score", 0.0))
    if score >= settings.AI_RELEVANCE_SUMMARIZE_THRESHOLD:
        return "relevant"
    if score < settings.AI_RELEVANCE_REVIEW_THRESHOLD:
        return "irrelevant"
    return "borderline"


def run_content_classification(content: Content) -> dict[str, Any]:
    if settings.OPENROUTER_API_KEY:
        try:
            response = openrouter_chat_json(
                model=settings.AI_CLASSIFICATION_MODEL,
                system_prompt=(
                    "You classify newsletter content into one of these categories: "
                    "technical_article, tutorial, opinion, product_announcement, event, release_notes, other. "
                    "Return JSON with content_type, confidence, and explanation."
                ),
                user_prompt=f"Title: {content.title}\nURL: {content.url}\n\nContent:\n{content.content_text[:5000]}",
            )
            payload = response.payload
            content_type = str(payload.get("content_type", "other"))
            if content_type not in CONTENT_TYPES:
                content_type = "other"
            confidence = _clamp_score(payload.get("confidence", 0.5))
            return {
                "content_type": content_type,
                "confidence": confidence,
                "explanation": str(payload.get("explanation", "LLM-based classification.")),
                "model_used": response.model,
                "latency_ms": response.latency_ms,
            }
        except Exception:
            logger.exception(
                "Classification model call failed; falling back to heuristic classifier",
                extra={"content_id": content.id},
            )
    return _heuristic_classification(content)


def run_relevance_scoring(content: Content) -> dict[str, Any]:
    vector = embed_text(build_content_embedding_text(content))
    similarity = float(get_reference_similarity(content.tenant_id, vector))
    if similarity >= settings.AI_RELEVANCE_HIGH_THRESHOLD or similarity < settings.AI_RELEVANCE_LOW_THRESHOLD:
        return {
            "relevance_score": similarity,
            "explanation": f"Reference corpus similarity score is {similarity:.2f}; no LLM adjudication was required.",
            "used_llm": False,
            "model_used": f"embedding:{settings.EMBEDDING_MODEL}",
            "latency_ms": 0,
        }

    if settings.OPENROUTER_API_KEY:
        try:
            response = openrouter_chat_json(
                model=settings.AI_RELEVANCE_MODEL,
                system_prompt=(
                    "You score how relevant a candidate article is for a newsletter topic. "
                    "Return JSON with relevance_score between 0 and 1, explanation, and used_llm=true."
                ),
                user_prompt=(
                    f"Newsletter topic: {content.tenant.topic_description}\n"
                    f"Reference similarity score: {similarity:.3f}\n"
                    f"Title: {content.title}\n"
                    f"Content:\n{content.content_text[:5000]}"
                ),
            )
            payload = response.payload
            return {
                "relevance_score": _clamp_score(payload.get("relevance_score", similarity)),
                "explanation": str(payload.get("explanation", "LLM-based relevance adjudication.")),
                "used_llm": True,
                "model_used": response.model,
                "latency_ms": response.latency_ms,
            }
        except Exception:
            logger.exception(
                "Relevance model call failed; falling back to heuristic relevance",
                extra={"content_id": content.id},
            )

    return {
        "relevance_score": similarity,
        "explanation": (
            f"Borderline reference similarity of {similarity:.2f} against the tenant baseline for "
            f"'{content.tenant.topic_description}'."
        ),
        "used_llm": False,
        "model_used": f"embedding:{settings.EMBEDDING_MODEL}",
        "latency_ms": 0,
    }


def run_summarization(content: Content) -> dict[str, Any]:
    if settings.OPENROUTER_API_KEY:
        try:
            response = openrouter_chat_json(
                model=settings.AI_SUMMARIZATION_MODEL,
                system_prompt=(
                    "You write concise newsletter-ready summaries. Return JSON with a single key named summary."
                ),
                user_prompt=(
                    f"Newsletter topic: {content.tenant.topic_description}\n"
                    f"Title: {content.title}\n"
                    f"Content:\n{content.content_text[:5000]}"
                ),
            )
            return {
                "summary": _normalize_summary(str(response.payload.get("summary", "")), content),
                "model_used": response.model,
                "latency_ms": response.latency_ms,
            }
        except Exception:
            logger.exception(
                "Summarization model call failed; falling back to heuristic summary",
                extra={"content_id": content.id},
            )
    return {
        "summary": _heuristic_summary(content),
        "model_used": "heuristic",
        "latency_ms": 0,
    }


def execute_ad_hoc_skill(content: Content, skill_name: str) -> SkillResult:
    if skill_name == CLASSIFICATION_SKILL_NAME:
        return _execute_ad_hoc_classification(content)
    if skill_name == RELEVANCE_SKILL_NAME:
        return _execute_ad_hoc_relevance(content)
    if skill_name == SUMMARIZATION_SKILL_NAME:
        return _execute_ad_hoc_summarization(content)
    if skill_name == RELATED_CONTENT_SKILL_NAME:
        return _execute_ad_hoc_related_content(content)
    raise ValueError(f"Unsupported skill name: {skill_name}")


def _execute_ad_hoc_classification(content: Content) -> SkillResult:
    try:
        classification = _execute_with_retries(CLASSIFICATION_SKILL_NAME, lambda: run_content_classification(content))
        content.content_type = classification["content_type"]
        content.save(update_fields=["content_type"])
        if classification["confidence"] < settings.AI_CLASSIFICATION_REVIEW_THRESHOLD:
            _upsert_review_queue_item(
                content,
                reason=ReviewReason.LOW_CONFIDENCE_CLASSIFICATION,
                confidence=float(classification["confidence"]),
            )
        return _create_skill_result(
            content,
            skill_name=CLASSIFICATION_SKILL_NAME,
            status=SkillStatus.COMPLETED,
            result_data=classification,
            model_used=classification["model_used"],
            latency_ms=classification["latency_ms"],
            confidence=classification["confidence"],
        )
    except Exception as exc:
        return _create_failed_skill_result(content, skill_name=CLASSIFICATION_SKILL_NAME, error_message=str(exc))


def _execute_ad_hoc_relevance(content: Content) -> SkillResult:
    try:
        relevance = _execute_with_retries(RELEVANCE_SKILL_NAME, lambda: run_relevance_scoring(content))
        relevance_score = float(relevance["relevance_score"])
        content.relevance_score = relevance_score
        content.is_active = relevance_score >= settings.AI_RELEVANCE_REVIEW_THRESHOLD
        content.save(update_fields=["relevance_score", "is_active"])
        if settings.AI_RELEVANCE_REVIEW_THRESHOLD <= relevance_score < settings.AI_RELEVANCE_SUMMARIZE_THRESHOLD:
            _upsert_review_queue_item(
                content,
                reason=ReviewReason.BORDERLINE_RELEVANCE,
                confidence=relevance_score,
            )
        return _create_skill_result(
            content,
            skill_name=RELEVANCE_SKILL_NAME,
            status=SkillStatus.COMPLETED,
            result_data=relevance,
            model_used=relevance["model_used"],
            latency_ms=relevance["latency_ms"],
            confidence=relevance_score,
        )
    except Exception as exc:
        return _create_failed_skill_result(content, skill_name=RELEVANCE_SKILL_NAME, error_message=str(exc))


def _execute_ad_hoc_summarization(content: Content) -> SkillResult:
    try:
        if (content.relevance_score or 0.0) < settings.AI_RELEVANCE_SUMMARIZE_THRESHOLD:
            raise ValueError(
                "Summarization requires relevance_score >= "
                f"{settings.AI_RELEVANCE_SUMMARIZE_THRESHOLD:.2f}. Run relevance scoring first or review the content."
            )
        summary = _execute_with_retries(SUMMARIZATION_SKILL_NAME, lambda: run_summarization(content))
        return _create_skill_result(
            content,
            skill_name=SUMMARIZATION_SKILL_NAME,
            status=SkillStatus.COMPLETED,
            result_data=summary,
            model_used=summary["model_used"],
            latency_ms=summary["latency_ms"],
        )
    except Exception as exc:
        return _create_failed_skill_result(content, skill_name=SUMMARIZATION_SKILL_NAME, error_message=str(exc))


def _execute_ad_hoc_related_content(content: Content) -> SkillResult:
    try:
        matches = search_similar_content(content, limit=5, is_reference=False)
        related_items = [_serialize_related_match(match) for match in matches]
        top_score = max((item["score"] for item in related_items), default=None)
        return _create_skill_result(
            content,
            skill_name=RELATED_CONTENT_SKILL_NAME,
            status=SkillStatus.COMPLETED,
            result_data={
                "related_items": related_items,
                "limit": 5,
            },
            model_used=f"embedding:{settings.EMBEDDING_MODEL}",
            latency_ms=0,
            confidence=top_score,
        )
    except Exception as exc:
        return _create_failed_skill_result(content, skill_name=RELATED_CONTENT_SKILL_NAME, error_message=str(exc))


def _execute_with_retries(skill_name: str, fn):
    last_exc: Exception | None = None
    for attempt in range(settings.AI_MAX_NODE_RETRIES + 1):
        try:
            return fn()
        except Exception as exc:  # pragma: no cover
            last_exc = exc
            logger.exception(
                "Skill execution failed",
                extra={"skill_name": skill_name, "attempt": attempt + 1},
            )
    assert last_exc is not None
    raise last_exc


def _serialize_related_match(match: Any) -> dict[str, Any]:
    payload = dict(getattr(match, "payload", {}) or {})
    return {
        "content_id": payload.get("content_id"),
        "title": payload.get("title"),
        "url": payload.get("url"),
        "published_date": payload.get("published_date"),
        "source_plugin": payload.get("source_plugin"),
        "score": float(getattr(match, "score", 0.0)),
    }


def _heuristic_classification(content: Content) -> dict[str, Any]:
    text = f"{content.title}\n{content.content_text}".lower()
    keyword_sets = {
        "release_notes": ("release notes", "changelog", "version", "released"),
        "tutorial": ("tutorial", "how to", "guide", "walkthrough", "step-by-step"),
        "product_announcement": ("announcing", "launch", "launched", "available now", "introducing"),
        "event": ("conference", "summit", "meetup", "webinar", "event"),
        "opinion": ("opinion", "why i", "lessons learned", "thoughts", "editorial"),
        "technical_article": ("architecture", "engineering", "platform", "infrastructure", "devops", "kubernetes"),
    }
    best_type = "other"
    best_score = 0
    for content_type, keywords in keyword_sets.items():
        score = sum(text.count(keyword) for keyword in keywords)
        if score > best_score:
            best_type = content_type
            best_score = score
    confidence = 0.45 if best_type == "other" else min(0.95, 0.55 + (best_score * 0.1))
    return {
        "content_type": best_type,
        "confidence": confidence,
        "explanation": "Keyword heuristic based on title and body text.",
        "model_used": "heuristic",
        "latency_ms": 0,
    }


def _heuristic_summary(content: Content) -> str:
    sentences = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", content.content_text.strip()) if segment.strip()]
    if not sentences:
        return f"{content.title}: no summary was available from the source content."
    summary = " ".join(sentences[:2])
    if len(summary) > 400:
        summary = summary[:397].rstrip() + "..."
    return _normalize_summary(summary, content)


def _normalize_summary(summary: str, content: Content) -> str:
    normalized = summary.strip()
    if normalized:
        return normalized
    return f"{content.title}: summary generation returned no content."


def _clamp_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = 0.0
    return max(0.0, min(1.0, score))


def _get_content(state: PipelineState) -> Content:
    return Content.objects.select_related("tenant").get(pk=state["content_id"])


def _upsert_review_queue_item(content: Content, *, reason: ReviewReason, confidence: float) -> ReviewQueue:
    existing = ReviewQueue.objects.filter(content=content, reason=reason, resolved=False).first()
    if existing:
        existing.confidence = confidence
        existing.save(update_fields=["confidence"])
        return existing
    return ReviewQueue.objects.create(
        tenant=content.tenant,
        content=content,
        reason=reason,
        confidence=confidence,
    )


def _create_skill_result(
    content: Content,
    *,
    skill_name: str,
    status: SkillStatus,
    result_data: dict[str, Any] | None = None,
    error_message: str = "",
    model_used: str = "",
    latency_ms: int | None = None,
    confidence: float | None = None,
) -> SkillResult:
    previous = SkillResult.objects.filter(content=content, skill_name=skill_name, superseded_by__isnull=True).first()
    skill_result = SkillResult.objects.create(
        content=content,
        tenant=content.tenant,
        skill_name=skill_name,
        status=status,
        result_data=result_data,
        error_message=error_message,
        model_used=model_used,
        latency_ms=latency_ms,
        confidence=confidence,
    )
    if previous:
        previous.superseded_by = skill_result
        previous.save(update_fields=["superseded_by"])
    return skill_result


def _create_failed_skill_result(content: Content, *, skill_name: str, error_message: str) -> SkillResult:
    return _create_skill_result(
        content,
        skill_name=skill_name,
        status=SkillStatus.FAILED,
        result_data=None,
        error_message=error_message,
    )
