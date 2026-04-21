from django.core.management.base import BaseCommand, CommandError

from core.embeddings import embed_text, upsert_content_embedding
from core.models import Content


class Command(BaseCommand):
    help = "Run a smoke check for the configured embedding provider."

    def add_arguments(self, parser):
        parser.add_argument(
            "--text",
            default="Platform engineering and DevOps content discovery",
            help="Text to embed for a provider smoke test.",
        )
        parser.add_argument(
            "--content-id",
            type=int,
            help="Optional content id to push through the full Qdrant upsert path.",
        )

    def handle(self, *args, **options):
        text = options["text"]
        content_id = options["content_id"]

        if content_id is not None:
            try:
                content = Content.objects.get(pk=content_id)
            except Content.DoesNotExist as exc:
                raise CommandError(f"Content with id {content_id} does not exist.") from exc
            embedding_id = upsert_content_embedding(content)
            self.stdout.write(self.style.SUCCESS(f"Upserted embedding for content {content_id}: {embedding_id}"))
            return

        vector = embed_text(text)
        preview = ", ".join(f"{value:.4f}" for value in vector[:5])
        self.stdout.write(self.style.SUCCESS(f"Embedding generated successfully. Dimension: {len(vector)}"))
        self.stdout.write(f"Preview: [{preview}]")