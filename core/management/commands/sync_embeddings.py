from django.core.management.base import BaseCommand, CommandError

from core.embeddings import upsert_content_embedding
from core.models import Content


class Command(BaseCommand):
    help = "Backfill Qdrant embeddings for content records."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-id", type=int, help="Only sync content for one tenant.")
        parser.add_argument("--content-id", type=int, help="Only sync one content record.")
        parser.add_argument(
            "--references-only",
            action="store_true",
            help="Only sync content marked as reference corpus items.",
        )

    def handle(self, *args, **options):
        queryset = Content.objects.select_related("tenant")
        if options["tenant_id"] is not None:
            queryset = queryset.filter(tenant_id=options["tenant_id"])
        if options["content_id"] is not None:
            queryset = queryset.filter(pk=options["content_id"])
        if options["references_only"]:
            queryset = queryset.filter(is_reference=True)

        if not queryset.exists():
            raise CommandError("No content records matched the requested scope.")

        synced_count = 0
        for content in queryset.iterator():
            upsert_content_embedding(content)
            synced_count += 1

        self.stdout.write(self.style.SUCCESS(f"Synced embeddings for {synced_count} content item(s)."))