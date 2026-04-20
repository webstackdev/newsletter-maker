from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed minimal demo data for the scaffold stage."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("WP7 seed data is not implemented yet."))
        self.stdout.write(self.style.SUCCESS("Scaffold seed command completed without changes."))