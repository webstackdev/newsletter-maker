import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from core.embeddings import upsert_content_embedding
from core.models import Content, IngestionRun, RunStatus, SourceConfig
from core.plugins import get_plugin_for_source_config


logger = logging.getLogger(__name__)


@shared_task(name="core.tasks.run_ingestion")
def run_ingestion(source_config_id: int):
    source_config = SourceConfig.objects.select_related("tenant").get(pk=source_config_id)
    ingestion_run = IngestionRun.objects.create(
        tenant=source_config.tenant,
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
        logger.exception("Source ingestion failed", extra={"source_config_id": source_config_id})
        raise

    ingestion_run.status = RunStatus.SUCCESS
    ingestion_run.completed_at = timezone.now()
    ingestion_run.items_fetched = items_fetched
    ingestion_run.items_ingested = items_ingested
    ingestion_run.save(update_fields=["status", "completed_at", "items_fetched", "items_ingested"])
    return {"items_fetched": items_fetched, "items_ingested": items_ingested}


@shared_task(name="core.tasks.run_all_ingestions")
def run_all_ingestions():
    source_config_ids = list(SourceConfig.objects.filter(is_active=True).values_list("id", flat=True))
    for source_config_id in source_config_ids:
        if settings.CELERY_TASK_ALWAYS_EAGER:
            run_ingestion(source_config_id)
        else:
            run_ingestion.delay(source_config_id)
    return len(source_config_ids)


def _ingest_source_config(source_config: SourceConfig) -> tuple[int, int]:
    plugin = get_plugin_for_source_config(source_config)
    fetched_items = plugin.fetch_new_content(source_config.last_fetched_at)
    ingested_count = 0
    for item in fetched_items:
        if Content.objects.filter(tenant=source_config.tenant, url=item.url).exists():
            continue
        content = Content.objects.create(
            tenant=source_config.tenant,
            entity=plugin.match_entity_for_url(item.url),
            url=item.url,
            title=item.title[:512],
            author=item.author[:255],
            source_plugin=item.source_plugin,
            published_date=item.published_date,
            content_text=item.content_text,
        )
        upsert_content_embedding(content)
        ingested_count += 1
    source_config.last_fetched_at = timezone.now()
    source_config.save(update_fields=["last_fetched_at"])
    return len(fetched_items), ingested_count