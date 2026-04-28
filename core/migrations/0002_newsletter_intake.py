from django.db import migrations, models
import django.db.models.deletion

import core.models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="intake_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="project",
            name="intake_token",
            field=models.CharField(default=core.models.generate_project_intake_token, editable=False, max_length=64, unique=True),
        ),
        migrations.AddField(
            model_name="content",
            name="source_metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.CreateModel(
            name="IntakeAllowlist",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sender_email", models.EmailField(max_length=254)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("confirmation_token", models.CharField(default=core.models.generate_confirmation_token, max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "project",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="intake_allowlist", to="core.project"),
                ),
            ],
            options={
                "ordering": ["sender_email"],
            },
        ),
        migrations.CreateModel(
            name="NewsletterIntake",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sender_email", models.EmailField(max_length=254)),
                ("subject", models.CharField(max_length=512)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("raw_html", models.TextField(blank=True)),
                ("raw_text", models.TextField(blank=True)),
                ("message_id", models.CharField(max_length=255, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("extracted", "Extracted"), ("failed", "Failed"), ("rejected", "Rejected")],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("extraction_result", models.JSONField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                (
                    "project",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="newsletter_intakes", to="core.project"),
                ),
            ],
            options={
                "ordering": ["-received_at"],
            },
        ),
        migrations.AddIndex(
            model_name="newsletterintake",
            index=models.Index(fields=["project", "sender_email", "status"], name="core_newsle_project_2c63fb_idx"),
        ),
        migrations.AddConstraint(
            model_name="intakeallowlist",
            constraint=models.UniqueConstraint(fields=("project", "sender_email"), name="core_allowlist_unique_project_sender"),
        ),
    ]