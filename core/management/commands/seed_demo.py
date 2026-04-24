from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.embeddings import upsert_content_embedding
from core.models import Content, SourcePluginName, Tenant, TenantConfig


REFERENCE_ARTICLES = [
    {
        "url": "https://example.com/reference/platform-engineering-golden-paths",
        "title": "Golden Paths for Platform Engineering Teams",
        "author": "Editorial Seed",
        "content_text": "Platform engineering teams reduce cognitive load by offering paved-road workflows, reusable deployment templates, and opinionated internal platforms.",
        "days_ago": 30,
    },
    {
        "url": "https://example.com/reference/kubernetes-release-practices",
        "title": "Kubernetes Release Engineering Lessons",
        "author": "Editorial Seed",
        "content_text": "Reliable Kubernetes operations depend on staged rollouts, workload health checks, and disciplined release engineering for platform teams.",
        "days_ago": 27,
    },
    {
        "url": "https://example.com/reference/devops-metrics",
        "title": "Measuring DevOps Performance Without Vanity Metrics",
        "author": "Editorial Seed",
        "content_text": "Useful DevOps metrics focus on deployment frequency, lead time, change failure rate, and recovery speed rather than noisy activity counts.",
        "days_ago": 24,
    },
    {
        "url": "https://example.com/reference/internal-developer-platforms",
        "title": "Internal Developer Platforms That Actually Help",
        "author": "Editorial Seed",
        "content_text": "An effective internal developer platform emphasizes self-service infrastructure, secure defaults, and operational clarity for engineering teams.",
        "days_ago": 21,
    },
    {
        "url": "https://example.com/reference/incident-review-culture",
        "title": "Incident Reviews That Improve Operations",
        "author": "Editorial Seed",
        "content_text": "Strong incident review practices improve resilience through blameless analysis, follow-through on action items, and better operational learning.",
        "days_ago": 18,
    },
]


SAMPLE_CONTENT = [
    {
        "url": "https://example.com/content/backstage-adoption",
        "title": "Backstage Adoption Patterns in Mid-Size Platform Teams",
        "author": "Alex Builder",
        "source_plugin": SourcePluginName.RSS,
        "content_text": "Teams adopting Backstage often start with service catalogs, software templates, and docs ownership to improve discoverability and reduce friction.",
        "days_ago": 5,
        "is_reference": False,
    },
    {
        "url": "https://example.com/content/argo-rollouts",
        "title": "Progressive Delivery with Argo Rollouts",
        "author": "Taylor Ops",
        "source_plugin": SourcePluginName.RSS,
        "content_text": "Progressive delivery helps platform teams validate rollouts with canaries, automated analysis, and safer release policies across Kubernetes workloads.",
        "days_ago": 4,
        "is_reference": False,
    },
    {
        "url": "https://example.com/content/cost-observability",
        "title": "FinOps Signals for Shared Platform Infrastructure",
        "author": "Jordan Cloud",
        "source_plugin": SourcePluginName.REDDIT,
        "content_text": "Shared platform teams need cost observability, ownership tagging, and usage feedback loops so product teams understand the cost of infrastructure choices.",
        "days_ago": 3,
        "is_reference": False,
    },
    {
        "url": "https://example.com/content/runbooks",
        "title": "Why Operational Runbooks Still Matter",
        "author": "Morgan Reliability",
        "source_plugin": SourcePluginName.RSS,
        "content_text": "Runbooks remain valuable when they are short, current, and tied to real incident response patterns instead of static documentation nobody trusts.",
        "days_ago": 2,
        "is_reference": False,
    },
]


class Command(BaseCommand):
    help = "Seed a demo tenant with a reference corpus and sample content for embeddings and Qdrant flows."

    def handle(self, *args, **options):
        with transaction.atomic():
            tenant = self._ensure_demo_tenant()
            reference_count = self._seed_articles(tenant, REFERENCE_ARTICLES, is_reference=True, source_plugin="reference_seed")
            sample_count = self._seed_articles(tenant, SAMPLE_CONTENT, is_reference=False)
            embedded_count = self._sync_embeddings(tenant)

        self.stdout.write(self.style.SUCCESS(f"Seeded demo tenant: {tenant.name}"))
        self.stdout.write(f"Reference corpus items: {reference_count}")
        self.stdout.write(f"Sample content items: {sample_count}")
        self.stdout.write(self.style.SUCCESS(f"Upserted embeddings for {embedded_count} content item(s)."))

    def _ensure_demo_tenant(self) -> Tenant:
        user_model = get_user_model()
        user, _ = user_model.objects.get_or_create(
            username="demo_editor",
            defaults={
                "email": "demo@example.com",
            },
        )
        user.set_password("demo-password")
        user.save(update_fields=["password"])

        tenant, created = Tenant.objects.get_or_create(
            user=user,
            name="Platform Engineering Weekly",
            defaults={
                "topic_description": "Platform engineering, DevOps, cloud infrastructure, reliability, and developer experience.",
            },
        )
        if not created and not tenant.topic_description:
            tenant.topic_description = "Platform engineering, DevOps, cloud infrastructure, reliability, and developer experience."
            tenant.save(update_fields=["topic_description"])
        TenantConfig.objects.get_or_create(tenant=tenant)
        return tenant

    def _seed_articles(self, tenant: Tenant, articles: list[dict], *, is_reference: bool, source_plugin: str | None = None) -> int:
        seeded_count = 0
        now = timezone.now()
        for article in articles:
            defaults = {
                "title": article["title"],
                "author": article["author"],
                "source_plugin": source_plugin or article["source_plugin"],
                "published_date": now - timedelta(days=article["days_ago"]),
                "content_text": article["content_text"],
                "is_reference": is_reference,
                "is_active": True,
            }
            Content.objects.update_or_create(
                tenant=tenant,
                url=article["url"],
                defaults=defaults,
            )
            seeded_count += 1
        return seeded_count

    def _sync_embeddings(self, tenant: Tenant) -> int:
        embedded_count = 0
        for content in Content.objects.filter(tenant=tenant).order_by("id"):
            upsert_content_embedding(content)
            embedded_count += 1
        return embedded_count