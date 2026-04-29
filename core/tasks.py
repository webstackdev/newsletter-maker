"""Celery tasks that drive ingestion, AI processing, and newsletter extraction."""

import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from core.embeddings import upsert_content_embedding
from core.models import (
    Content,
    IngestionRun,
    IntakeAllowlist,
    NewsletterIntake,
    NewsletterIntakeStatus,
    RunStatus,
    SourceConfig,
)
from core.newsletter_extraction import extract_newsletter_items
from core.pipeline import (
    RELEVANCE_SKILL_NAME,
    SUMMARIZATION_SKILL_NAME,
    create_pending_skill_result,
    execute_background_skill_result,
    process_content_pipeline,
)
from core.plugins import get_plugin_for_source_config

logger = logging.getLogger(__name__)


@shared_task(name="core.tasks.run_ingestion")
def run_ingestion(source_config_id: int):
    """Fetch new content for one source config and record an ingestion run.

    Args:
        source_config_id: Primary key of the source configuration to ingest.

    Returns:
        A summary containing fetched and ingested item counts.
    """

    source_config = SourceConfig.objects.select_related("project").get(
        pk=source_config_id
    )
    ingestion_run = IngestionRun.objects.create(
        project=source_config.project,
        plugin_name=source_config.plugin_name,
        status=RunStatus.RUNNING,
    )
    try:
        items_fetched, items_ingested = _ingest_source_config(source_config)
    except Exception as exc:
        ingestion_run.status = RunStatus.FAILED
        ingestion_run.completed_at = timezone.now()
        ingestion_run.error_message = str(exc)
        ingestion_run.save(update_fields=["status", "completed_at", "error_message"])
        logger.exception(
            "Source ingestion failed", extra={"source_config_id": source_config_id}
        )
        raise

    ingestion_run.status = RunStatus.SUCCESS
    ingestion_run.completed_at = timezone.now()
    ingestion_run.items_fetched = items_fetched
    ingestion_run.items_ingested = items_ingested
    ingestion_run.save(
        update_fields=["status", "completed_at", "items_fetched", "items_ingested"]
    )
    return {"items_fetched": items_fetched, "items_ingested": items_ingested}


@shared_task(name="core.tasks.run_all_ingestions")
def run_all_ingestions():
    """Queue ingestion for every active source configuration.

    Returns:
        The number of source configurations scheduled.
    """

    source_config_ids = list(
        SourceConfig.objects.filter(is_active=True).values_list("id", flat=True)
    )
    for source_config_id in source_config_ids:
        if settings.CELERY_TASK_ALWAYS_EAGER:
            run_ingestion(source_config_id)
        else:
            run_ingestion.delay(source_config_id)
    return len(source_config_ids)


@shared_task(name="core.tasks.process_content")
def process_content(content_id: int):
    """Run the main AI pipeline for a stored content item."""

    return process_content_pipeline(content_id)


@shared_task(name="core.tasks.run_relevance_scoring_skill", ignore_result=True)
def run_relevance_scoring_skill(skill_result_id: int):
    """Execute a pending ad hoc relevance skill result in the background."""

    return execute_background_skill_result(skill_result_id, RELEVANCE_SKILL_NAME)


@shared_task(name="core.tasks.run_summarization_skill", ignore_result=True)
def run_summarization_skill(skill_result_id: int):
    """Execute a pending ad hoc summarization skill result in the background."""

    return execute_background_skill_result(skill_result_id, SUMMARIZATION_SKILL_NAME)


def queue_content_skill(content: Content, skill_name: str):
    """Create and dispatch an asynchronous ad hoc skill for a content row.

    Args:
        content: The content row to process.
        skill_name: Supported async skill name.

    Returns:
        The refreshed ``SkillResult`` row after the task has been queued or eagerly
        executed.
    """

    skill_result = create_pending_skill_result(content, skill_name)

    if skill_name == RELEVANCE_SKILL_NAME:
        if settings.CELERY_TASK_ALWAYS_EAGER:
            run_relevance_scoring_skill(skill_result.id)
        else:
            run_relevance_scoring_skill.delay(skill_result.id)
    elif skill_name == SUMMARIZATION_SKILL_NAME:
        if settings.CELERY_TASK_ALWAYS_EAGER:
            run_summarization_skill(skill_result.id)
        else:
            run_summarization_skill.delay(skill_result.id)
    else:
        raise ValueError(f"Unsupported async skill name: {skill_name}")

    skill_result.refresh_from_db()
    return skill_result


def _ingest_source_config(source_config: SourceConfig) -> tuple[int, int]:
    """Fetch items from a configured source and create new content rows."""

    plugin = get_plugin_for_source_config(source_config)
    fetched_items = plugin.fetch_new_content(source_config.last_fetched_at)
    ingested_count = 0
    for item in fetched_items:
        if _content_exists_for_item(source_config, item):
            continue
        source_metadata = getattr(item, "source_metadata", None) or {}
        content = Content.objects.create(
            project=source_config.project,
            entity=_match_entity_for_item(plugin, item),
            url=item.url,
            title=item.title[:512],
            author=item.author[:255],
            source_plugin=item.source_plugin,
            published_date=item.published_date,
            content_text=item.content_text,
            source_metadata=source_metadata,
        )
        _schedule_content_processing(content)
        ingested_count += 1
    source_config.last_fetched_at = timezone.now()
    source_config.save(update_fields=["last_fetched_at"])
    return len(fetched_items), ingested_count


def _content_exists_for_item(source_config: SourceConfig, item) -> bool:
    """Check whether a fetched item already exists for the project."""

    post_uri = (getattr(item, "source_metadata", None) or {}).get("post_uri")
    if post_uri:
        return Content.objects.filter(
            project=source_config.project,
            source_plugin=item.source_plugin,
            source_metadata__post_uri=post_uri,
        ).exists()
    return Content.objects.filter(project=source_config.project, url=item.url).exists()


def _match_entity_for_item(plugin, item):
    """Resolve the entity for an item while preserving older plugin mocks."""

    if callable(getattr(type(plugin), "match_entity_for_item", None)):
        return plugin.match_entity_for_item(item)
    return plugin.match_entity_for_url(item.url)


@shared_task(name="core.tasks.process_newsletter_intake")
def process_newsletter_intake(intake_id: int):
    """Convert a stored newsletter email into content rows.

    Args:
        intake_id: Primary key of the ``NewsletterIntake`` row to process.

    Returns:
        A summary containing the final intake status and ingested item count.
    """

    intake = NewsletterIntake.objects.select_related("project").get(pk=intake_id)

    allowlist = IntakeAllowlist.objects.filter(
        project=intake.project,
        sender_email=intake.sender_email,
        confirmed_at__isnull=False,
    ).first()
    if allowlist is None:
        intake.status = NewsletterIntakeStatus.PENDING
        intake.error_message = "Sender has not confirmed newsletter intake."
        intake.save(update_fields=["status", "error_message"])
        return {"status": intake.status, "items_ingested": 0}

    extracted_items = extract_newsletter_items(
        subject=intake.subject,
        raw_html=intake.raw_html,
        raw_text=intake.raw_text,
    )
    ingested_count = 0
    for item in extracted_items:
        if Content.objects.filter(project=intake.project, url=item.url).exists():
            continue
        content = Content.objects.create(
            project=intake.project,
            url=item.url,
            title=item.title[:512],
            author=intake.sender_email[:255],
            source_plugin="newsletter",
            published_date=timezone.now(),
            content_text=item.excerpt or intake.raw_text,
            source_metadata={
                "newsletter_intake_id": intake.id,
                "sender_email": intake.sender_email,
                "position": item.position,
            },
        )
        _schedule_content_processing(content)
        ingested_count += 1

    intake.status = NewsletterIntakeStatus.EXTRACTED
    intake.error_message = ""
    intake.extraction_result = {
        "method": "heuristic",
        "items": [
            {
                "url": item.url,
                "title": item.title,
                "excerpt": item.excerpt,
                "position": item.position,
            }
            for item in extracted_items
        ],
    }
    intake.save(update_fields=["status", "error_message", "extraction_result"])
    return {"status": intake.status, "items_ingested": ingested_count}


def _schedule_content_processing(content: Content) -> None:
    """Ensure a content row is embedded before it enters the AI pipeline."""

    upsert_content_embedding(content)
    if settings.CELERY_TASK_ALWAYS_EAGER:
        process_content(content.id)
    else:
        process_content.delay(content.id)
