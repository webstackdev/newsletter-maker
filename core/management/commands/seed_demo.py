from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from httpx import HTTPError
from qdrant_client.http.exceptions import ResponseHandlingException

from core.embeddings import upsert_content_embedding
from core.models import (
    Content,
    Entity,
    EntityType,
    FeedbackType,
    IngestionRun,
    ReviewQueue,
    ReviewReason,
    ReviewResolution,
    RunStatus,
    SkillResult,
    SkillStatus,
    SourceConfig,
    SourcePluginName,
    Tenant,
    TenantConfig,
    UserFeedback,
)
from core.pipeline import (
    CLASSIFICATION_SKILL_NAME,
    RELEVANCE_SKILL_NAME,
    SUMMARIZATION_SKILL_NAME,
)

DEMO_TENANT_NAME = "Platform Engineering Weekly"
DEMO_TOPIC_DESCRIPTION = (
    "Platform engineering, DevOps, cloud infrastructure, reliability, and "
    "developer experience."
)
REFERENCE_SOURCE_PLUGIN = "reference_seed"

ENTITY_SPECS = [
    {
        "name": "Kelsey Hightower",
        "type": EntityType.INDIVIDUAL,
        "description": "Cloud infrastructure educator and platform engineering voice.",
        "authority_score": 0.94,
        "website_url": "https://example.com/entities/kelsey-hightower",
        "twitter_handle": "kelseyhightower",
    },
    {
        "name": "Charity Majors",
        "type": EntityType.INDIVIDUAL,
        "description": "Observability and DevOps leadership commentator.",
        "authority_score": 0.91,
        "website_url": "https://example.com/entities/charity-majors",
        "twitter_handle": "mipsytipsy",
    },
    {
        "name": "Liz Rice",
        "type": EntityType.INDIVIDUAL,
        "description": "Container security and Kubernetes runtime expert.",
        "authority_score": 0.89,
        "website_url": "https://example.com/entities/liz-rice",
        "twitter_handle": "lizrice",
    },
    {
        "name": "Mitchell Hashimoto",
        "type": EntityType.INDIVIDUAL,
        "description": "Infrastructure workflow builder and platform tooling founder.",
        "authority_score": 0.9,
        "website_url": "https://example.com/entities/mitchell-hashimoto",
        "twitter_handle": "mitchellh",
    },
    {
        "name": "Solomon Hykes",
        "type": EntityType.INDIVIDUAL,
        "description": "Container ecosystem pioneer with platform automation perspective.",
        "authority_score": 0.86,
        "website_url": "https://example.com/entities/solomon-hykes",
        "twitter_handle": "solomonstre",
    },
    {
        "name": "Abby Bangser",
        "type": EntityType.INDIVIDUAL,
        "description": "Progressive delivery and reliable release operations advocate.",
        "authority_score": 0.83,
        "website_url": "https://example.com/entities/abby-bangser",
        "twitter_handle": "abangser",
    },
    {
        "name": "Viktor Farcic",
        "type": EntityType.INDIVIDUAL,
        "description": "Kubernetes automation educator and GitOps practitioner.",
        "authority_score": 0.82,
        "website_url": "https://example.com/entities/viktor-farcic",
        "twitter_handle": "vfarcic",
    },
    {
        "name": "Paula Kennedy",
        "type": EntityType.INDIVIDUAL,
        "description": "Platform operations leader focused on delivery systems and DX.",
        "authority_score": 0.8,
        "website_url": "https://example.com/entities/paula-kennedy",
        "twitter_handle": "paulapkennedy",
    },
    {
        "name": "HashiCorp",
        "type": EntityType.VENDOR,
        "description": "Infrastructure lifecycle tooling vendor.",
        "authority_score": 0.9,
        "website_url": "https://example.com/vendors/hashicorp",
        "github_url": "https://github.com/hashicorp",
    },
    {
        "name": "Datadog",
        "type": EntityType.VENDOR,
        "description": "Observability platform vendor.",
        "authority_score": 0.88,
        "website_url": "https://example.com/vendors/datadog",
        "github_url": "https://github.com/DataDog",
    },
    {
        "name": "Grafana Labs",
        "type": EntityType.VENDOR,
        "description": "Monitoring and observability tooling vendor.",
        "authority_score": 0.87,
        "website_url": "https://example.com/vendors/grafana-labs",
        "github_url": "https://github.com/grafana",
    },
    {
        "name": "Vercel",
        "type": EntityType.VENDOR,
        "description": "Deployment platform vendor with developer productivity focus.",
        "authority_score": 0.76,
        "website_url": "https://example.com/vendors/vercel",
        "github_url": "https://github.com/vercel",
    },
    {
        "name": "Jetstack",
        "type": EntityType.VENDOR,
        "description": "Cloud native platform security and certificate tooling vendor.",
        "authority_score": 0.79,
        "website_url": "https://example.com/vendors/jetstack",
        "github_url": "https://github.com/jetstack",
    },
    {
        "name": "CNCF",
        "type": EntityType.ORGANIZATION,
        "description": "Cloud Native Computing Foundation ecosystem steward.",
        "authority_score": 0.95,
        "website_url": "https://example.com/orgs/cncf",
    },
    {
        "name": "Linux Foundation",
        "type": EntityType.ORGANIZATION,
        "description": "Open source foundation behind major infrastructure ecosystems.",
        "authority_score": 0.92,
        "website_url": "https://example.com/orgs/linux-foundation",
    },
]

SOURCE_CONFIG_SPECS = [
    {
        "plugin_name": SourcePluginName.RSS,
        "config": {"feed_url": "https://platformweekly.example.com/feed.xml"},
        "is_active": True,
        "hours_ago": 3,
    },
    {
        "plugin_name": SourcePluginName.RSS,
        "config": {"feed_url": "https://engineering.hashicorp.example.com/feed.xml"},
        "is_active": True,
        "hours_ago": 5,
    },
    {
        "plugin_name": SourcePluginName.RSS,
        "config": {"feed_url": "https://observability.datadog.example.com/feed.xml"},
        "is_active": True,
        "hours_ago": 7,
    },
    {
        "plugin_name": SourcePluginName.RSS,
        "config": {"feed_url": "https://grafana.example.com/feed.xml"},
        "is_active": True,
        "hours_ago": 11,
    },
    {
        "plugin_name": SourcePluginName.RSS,
        "config": {"feed_url": "https://linuxfoundation.example.com/feed.xml"},
        "is_active": False,
        "hours_ago": None,
    },
    {
        "plugin_name": SourcePluginName.RSS,
        "config": {"feed_url": "https://jetstack.example.com/feed.xml"},
        "is_active": True,
        "hours_ago": 15,
    },
    {
        "plugin_name": SourcePluginName.REDDIT,
        "config": {"subreddit": "devops", "listing": "hot", "limit": 25},
        "is_active": True,
        "hours_ago": 2,
    },
    {
        "plugin_name": SourcePluginName.REDDIT,
        "config": {"subreddit": "kubernetes", "listing": "new", "limit": 25},
        "is_active": True,
        "hours_ago": 4,
    },
]

LEGACY_REFERENCE_ARTICLES = [
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

REFERENCE_TOPICS = [
    {
        "slug": "golden-path-adoption",
        "title": "Golden Path Adoption in Growing Engineering Orgs",
        "content": "Teams get more value from platform programs when paved-road workflows, self-service actions, and clear ownership boundaries are introduced together.",
    },
    {
        "slug": "cluster-upgrades",
        "title": "How Mature Teams De-Risk Cluster Upgrades",
        "content": "Healthy platform groups stage Kubernetes upgrades with preflight checks, workload canaries, and explicit rollback steps that application teams can trust.",
    },
    {
        "slug": "delivery-metrics",
        "title": "Delivery Metrics That Actually Change Engineering Behavior",
        "content": "The most useful delivery scorecards connect lead time and incident recovery to engineering systems, not vanity measures or ticket volume.",
    },
    {
        "slug": "developer-portals",
        "title": "Developer Portals Need Service Ownership to Work",
        "content": "Catalog quality improves when developer portals tie service metadata, docs, and alert ownership into one operating model.",
    },
    {
        "slug": "incident-command",
        "title": "Incident Command Patterns for Platform Teams",
        "content": "Clear command roles, live timelines, and action-item follow-through help platform teams improve reliability under pressure.",
    },
    {
        "slug": "runbook-quality",
        "title": "Operational Runbooks That Stay Useful",
        "content": "Runbooks remain valuable when they are tested during drills, written for the pager path, and updated alongside the services they describe.",
    },
    {
        "slug": "cost-visibility",
        "title": "Shared Infrastructure Needs Cost Visibility",
        "content": "FinOps discipline improves when platform teams expose ownership tags, service-by-service usage, and visible cost trade-offs for engineering choices.",
    },
    {
        "slug": "release-policy",
        "title": "Release Policies That Scale Without Bureaucracy",
        "content": "Release systems stay fast when guardrails are automated, exceptions are visible, and change risk is measured instead of guessed.",
    },
    {
        "slug": "platform-adoption",
        "title": "Measuring Internal Platform Adoption Beyond Login Counts",
        "content": "Adoption signals are strongest when teams can complete real workflows faster, with fewer support tickets and less cognitive overhead.",
    },
]

LEGACY_SAMPLE_CONTENT = [
    {
        "url": "https://example.com/content/backstage-adoption",
        "title": "Backstage Adoption Patterns in Mid-Size Platform Teams",
        "author": "Alex Builder",
        "source_plugin": SourcePluginName.RSS,
        "content_text": "Teams adopting Backstage often start with service catalogs, software templates, and docs ownership to improve discoverability and reduce friction.",
        "days_ago": 5,
        "content_type": "technical_article",
        "classification_confidence": 0.88,
        "relevance_score": 0.91,
        "entity_name": "CNCF",
    },
    {
        "url": "https://example.com/content/argo-rollouts",
        "title": "Progressive Delivery with Argo Rollouts",
        "author": "Taylor Ops",
        "source_plugin": SourcePluginName.RSS,
        "content_text": "Progressive delivery helps platform teams validate rollouts with canaries, automated analysis, and safer release policies across Kubernetes workloads.",
        "days_ago": 4,
        "content_type": "tutorial",
        "classification_confidence": 0.9,
        "relevance_score": 0.87,
        "entity_name": "CNCF",
    },
    {
        "url": "https://example.com/content/cost-observability",
        "title": "FinOps Signals for Shared Platform Infrastructure",
        "author": "Jordan Cloud",
        "source_plugin": SourcePluginName.REDDIT,
        "content_text": "Shared platform teams need cost observability, ownership tagging, and usage feedback loops so product teams understand the cost of infrastructure choices.",
        "days_ago": 3,
        "content_type": "technical_article",
        "classification_confidence": 0.81,
        "relevance_score": 0.82,
        "entity_name": None,
    },
    {
        "url": "https://example.com/content/runbooks",
        "title": "Why Operational Runbooks Still Matter",
        "author": "Morgan Reliability",
        "source_plugin": SourcePluginName.RSS,
        "content_text": "Runbooks remain valuable when they are short, current, and tied to real incident response patterns instead of static documentation nobody trusts.",
        "days_ago": 2,
        "content_type": "opinion",
        "classification_confidence": 0.67,
        "relevance_score": 0.79,
        "entity_name": "Linux Foundation",
    },
]

RSS_PUBLICATIONS = [
    {
        "label": "Platform Weekly",
        "host": "platformweekly.example.com",
        "entity_name": "CNCF",
    },
    {
        "label": "HashiCorp Engineering",
        "host": "engineering.hashicorp.example.com",
        "entity_name": "HashiCorp",
    },
    {
        "label": "Datadog Observability",
        "host": "observability.datadog.example.com",
        "entity_name": "Datadog",
    },
    {
        "label": "Grafana Labs Blog",
        "host": "grafana.example.com",
        "entity_name": "Grafana Labs",
    },
    {
        "label": "Linux Foundation Engineering",
        "host": "linuxfoundation.example.com",
        "entity_name": "Linux Foundation",
    },
    {
        "label": "Jetstack Updates",
        "host": "jetstack.example.com",
        "entity_name": "Jetstack",
    },
]

RSS_TOPIC_BLUEPRINTS = [
    {
        "slug": "golden-path-templates",
        "headline": "Golden-path templates reduce setup time for platform teams",
        "content_type": "technical_article",
        "body": "The piece explains how reusable templates, service metadata, and sensible defaults give teams a faster path to production.",
    },
    {
        "slug": "progressive-delivery",
        "headline": "Progressive delivery patterns for shared Kubernetes platforms",
        "content_type": "tutorial",
        "body": "It walks through canary rollouts, automated checks, and ownership boundaries that make releases safer without slowing delivery.",
    },
    {
        "slug": "cost-guardrails",
        "headline": "Cost guardrails for internal developer platforms",
        "content_type": "technical_article",
        "body": "The article focuses on usage visibility, quota design, and the small control loops teams need to keep infrastructure spend understandable.",
    },
    {
        "slug": "runbook-culture",
        "headline": "Runbook maintenance is still a platform engineering advantage",
        "content_type": "opinion",
        "body": "It argues that concise runbooks and on-call practice still outperform sprawling internal wikis when incidents are unfolding quickly.",
    },
    {
        "slug": "backstage-ownership",
        "headline": "Developer portals work best when ownership data is real",
        "content_type": "technical_article",
        "body": "The story connects service catalogs, docs ownership, and scorecards to actual adoption rather than passive documentation projects.",
    },
    {
        "slug": "cluster-lifecycle",
        "headline": "Cluster lifecycle policies for platform teams under growth",
        "content_type": "release_notes",
        "body": "The author covers upgrade pacing, deprecation messaging, and health gates that help teams standardize their operating model.",
    },
    {
        "slug": "internal-developer-platform",
        "headline": "Internal developer platform scope is easier to manage with paved roads",
        "content_type": "technical_article",
        "body": "It emphasizes clear boundaries, supported workflows, and fast documentation paths so teams can adopt the platform intentionally.",
    },
    {
        "slug": "incident-learning",
        "headline": "Incident review loops that strengthen platform reliability",
        "content_type": "technical_article",
        "body": "This write-up connects post-incident review habits to architecture decisions, ownership, and change-risk management.",
    },
]

REDDIT_COMMUNITIES = ["devops", "kubernetes"]
REDDIT_TOPIC_BLUEPRINTS = [
    {
        "slug": "helm-ownership",
        "headline": "Teams debate who should own Helm charts for shared services",
        "content_type": "opinion",
        "body": "Commenters compare central platform ownership with service-team autonomy and trade stories about chart maintenance drift.",
    },
    {
        "slug": "cost-visibility",
        "headline": "Practitioners share how they expose platform costs to app teams",
        "content_type": "technical_article",
        "body": "The thread surfaces tactics for chargeback dashboards, tagging, and budget guardrails that teams actually act on.",
    },
    {
        "slug": "cluster-upgrades",
        "headline": "What broke during your last cluster upgrade window?",
        "content_type": "other",
        "body": "Respondents compare controller drift, workload surprises, and the safeguards that made the next upgrade less painful.",
    },
    {
        "slug": "runbooks",
        "headline": "Engineers compare runbook formats that still help under pressure",
        "content_type": "other",
        "body": "The discussion covers how short, actionable runbooks outperform static documentation in real incident response.",
    },
    {
        "slug": "platform-roadmaps",
        "headline": "How do you keep platform roadmaps aligned with developer pain?",
        "content_type": "opinion",
        "body": "People discuss surveys, support queues, and advisory groups as ways to keep platform work grounded in real friction.",
    },
    {
        "slug": "delivery-speed",
        "headline": "Where do you measure deployment speed without gaming the metric?",
        "content_type": "technical_article",
        "body": "The conversation compares lead time, failure rate, and service ownership as stronger measures than ticket throughput.",
    },
]


class Command(BaseCommand):
    help = "Seed a deterministic demo tenant with entities, content, pipeline outputs, feedback, and ingestion history."

    def handle(self, *args, **options):
        reference_articles = self._build_reference_articles()
        sample_articles = self._build_demo_content()

        with transaction.atomic():
            tenant = self._ensure_demo_tenant()
            self._reset_demo_runtime_state(tenant)
            entity_map = self._seed_entities(tenant)
            source_config_count = self._seed_source_configs(tenant)
            reference_contents = self._seed_articles(
                tenant,
                reference_articles,
                entity_map,
                is_reference=True,
                source_plugin=REFERENCE_SOURCE_PLUGIN,
            )
            sample_contents = self._seed_articles(
                tenant,
                sample_articles,
                entity_map,
                is_reference=False,
            )
            skill_result_count, review_count = self._seed_pipeline_state(
                tenant,
                sample_articles,
                sample_contents,
            )
            feedback_count = self._seed_feedback(tenant, sample_contents)
            ingestion_run_count = self._seed_ingestion_runs(tenant)
            embedded_count = self._sync_embeddings(reference_contents + sample_contents)

        self.stdout.write(self.style.SUCCESS(f"Seeded demo tenant: {tenant.name}"))
        self.stdout.write(f"Entities: {len(entity_map)}")
        self.stdout.write(f"Source configs: {source_config_count}")
        self.stdout.write(f"Reference corpus items: {len(reference_contents)}")
        self.stdout.write(f"Demo content items: {len(sample_contents)}")
        self.stdout.write(f"Skill results: {skill_result_count}")
        self.stdout.write(f"Review queue items: {review_count}")
        self.stdout.write(f"Feedback items: {feedback_count}")
        self.stdout.write(f"Ingestion runs: {ingestion_run_count}")
        self.stdout.write(
            self.style.SUCCESS(
                f"Upserted embeddings for {embedded_count} seeded content item(s)."
            )
        )

    def _ensure_demo_tenant(self) -> Tenant:
        user_model = get_user_model()
        user, _ = user_model.objects.get_or_create(
            username="demo_editor",
            defaults={"email": "demo@example.com"},
        )
        user.set_password("demo-password")
        user.save(update_fields=["password"])

        tenant, created = Tenant.objects.get_or_create(
            user=user,
            name=DEMO_TENANT_NAME,
            defaults={"topic_description": DEMO_TOPIC_DESCRIPTION},
        )
        if not created and tenant.topic_description != DEMO_TOPIC_DESCRIPTION:
            tenant.topic_description = DEMO_TOPIC_DESCRIPTION
            tenant.save(update_fields=["topic_description"])
        TenantConfig.objects.get_or_create(tenant=tenant)
        return tenant

    def _reset_demo_runtime_state(self, tenant: Tenant) -> None:
        SkillResult.objects.filter(tenant=tenant).delete()
        ReviewQueue.objects.filter(tenant=tenant).delete()
        UserFeedback.objects.filter(tenant=tenant).delete()
        IngestionRun.objects.filter(tenant=tenant).delete()
        SourceConfig.objects.filter(tenant=tenant).delete()

    def _seed_entities(self, tenant: Tenant) -> dict[str, Entity]:
        entities_by_name: dict[str, Entity] = {}
        for spec in ENTITY_SPECS:
            defaults = {
                "type": spec["type"],
                "description": spec["description"],
                "authority_score": spec["authority_score"],
                "website_url": spec.get("website_url", ""),
                "github_url": spec.get("github_url", ""),
                "linkedin_url": spec.get("linkedin_url", ""),
                "bluesky_handle": spec.get("bluesky_handle", ""),
                "mastodon_handle": spec.get("mastodon_handle", ""),
                "twitter_handle": spec.get("twitter_handle", ""),
            }
            entity, _ = Entity.objects.update_or_create(
                tenant=tenant,
                name=spec["name"],
                defaults=defaults,
            )
            entities_by_name[entity.name] = entity
        return entities_by_name

    def _seed_source_configs(self, tenant: Tenant) -> int:
        now = timezone.now()
        for spec in SOURCE_CONFIG_SPECS:
            hours_ago = cast(int | None, spec["hours_ago"])
            last_fetched_at = None
            if hours_ago is not None:
                last_fetched_at = now - timedelta(hours=hours_ago)
            SourceConfig.objects.create(
                tenant=tenant,
                plugin_name=cast(str, spec["plugin_name"]),
                config=spec["config"],
                is_active=cast(bool, spec["is_active"]),
                last_fetched_at=last_fetched_at,
            )
        return len(SOURCE_CONFIG_SPECS)

    def _seed_articles(
        self,
        tenant: Tenant,
        articles: list[dict[str, Any]],
        entities_by_name: dict[str, Entity],
        *,
        is_reference: bool,
        source_plugin: str | None = None,
    ) -> list[Content]:
        now = timezone.now()
        seeded_contents: list[Content] = []
        for article in articles:
            defaults = {
                "title": article["title"],
                "author": article["author"],
                "entity": entities_by_name.get(article.get("entity_name", "")),
                "source_plugin": source_plugin or article["source_plugin"],
                "published_date": now - timedelta(days=article["days_ago"]),
                "content_text": article["content_text"],
                "is_reference": is_reference,
                "is_active": True,
            }
            content, _ = Content.objects.update_or_create(
                tenant=tenant,
                url=article["url"],
                defaults=defaults,
            )
            seeded_contents.append(content)
        return seeded_contents

    def _seed_pipeline_state(
        self,
        tenant: Tenant,
        article_specs: list[dict[str, Any]],
        contents: list[Content],
    ) -> tuple[int, int]:
        content_by_url = {content.url: content for content in contents}
        content_updates: list[Content] = []
        skill_results: list[SkillResult] = []
        review_items: list[ReviewQueue] = []

        for index, article in enumerate(article_specs):
            content = content_by_url[article["url"]]
            classification_confidence = float(article["classification_confidence"])
            relevance_score = float(article["relevance_score"])
            review_reason = self._review_reason_for_article(
                classification_confidence,
                relevance_score,
            )
            content.content_type = article["content_type"]
            content.relevance_score = relevance_score
            content.is_active = relevance_score >= settings.AI_RELEVANCE_REVIEW_THRESHOLD
            content_updates.append(content)

            skill_results.append(
                SkillResult(
                    content=content,
                    tenant=tenant,
                    skill_name=CLASSIFICATION_SKILL_NAME,
                    status=SkillStatus.COMPLETED,
                    result_data={
                        "content_type": article["content_type"],
                        "confidence": classification_confidence,
                        "explanation": self._classification_explanation(article),
                    },
                    model_used=settings.AI_CLASSIFICATION_MODEL,
                    latency_ms=240 + (index % 5) * 35,
                    confidence=classification_confidence,
                )
            )
            skill_results.append(
                SkillResult(
                    content=content,
                    tenant=tenant,
                    skill_name=RELEVANCE_SKILL_NAME,
                    status=SkillStatus.COMPLETED,
                    result_data={
                        "relevance_score": relevance_score,
                        "explanation": self._relevance_explanation(article),
                        "used_llm": bool(article.get("used_llm", False)),
                    },
                    model_used=self._relevance_model_used(article),
                    latency_ms=(
                        0
                        if not article.get("used_llm", False)
                        else 900 + (index % 4) * 120
                    ),
                    confidence=relevance_score,
                )
            )
            if relevance_score >= settings.AI_RELEVANCE_SUMMARIZE_THRESHOLD:
                skill_results.append(
                    SkillResult(
                        content=content,
                        tenant=tenant,
                        skill_name=SUMMARIZATION_SKILL_NAME,
                        status=SkillStatus.COMPLETED,
                        result_data={
                            "summary": self._summary_for_article(article),
                        },
                        model_used=settings.AI_SUMMARIZATION_MODEL,
                        latency_ms=640 + (index % 6) * 40,
                    )
                )
            if review_reason is not None:
                resolved = index % 6 == 0
                resolution = ""
                if resolved:
                    resolution = (
                        ReviewResolution.HUMAN_APPROVED
                        if relevance_score >= settings.AI_RELEVANCE_REVIEW_THRESHOLD
                        else ReviewResolution.HUMAN_REJECTED
                    )
                confidence = (
                    classification_confidence
                    if review_reason == ReviewReason.LOW_CONFIDENCE_CLASSIFICATION
                    else relevance_score
                )
                review_items.append(
                    ReviewQueue(
                        tenant=tenant,
                        content=content,
                        reason=review_reason,
                        confidence=confidence,
                        resolved=resolved,
                        resolution=resolution,
                    )
                )

        Content.objects.bulk_update(
            content_updates,
            ["content_type", "relevance_score", "is_active"],
        )
        SkillResult.objects.bulk_create(skill_results)
        ReviewQueue.objects.bulk_create(review_items)
        return len(skill_results), len(review_items)

    def _seed_feedback(self, tenant: Tenant, contents: list[Content]) -> int:
        user_model = get_user_model()
        voters = []
        for index in range(1, 7):
            user, _ = user_model.objects.get_or_create(
                username=f"demo_reader_{index}",
                defaults={"email": f"demo-reader-{index}@example.com"},
            )
            user.set_password("demo-password")
            user.save(update_fields=["password"])
            voters.append(user)

        active_contents = sorted(
            [content for content in contents if content.is_active],
            key=lambda content: (content.relevance_score or 0.0, content.published_date),
            reverse=True,
        )
        feedback_count = 0

        for index, content in enumerate(active_contents[:30]):
            UserFeedback.objects.update_or_create(
                content=content,
                user=voters[index % len(voters)],
                defaults={
                    "tenant": tenant,
                    "feedback_type": FeedbackType.UPVOTE,
                },
            )
            feedback_count += 1

        for index, content in enumerate(active_contents[-15:]):
            UserFeedback.objects.update_or_create(
                content=content,
                user=voters[(index + 2) % len(voters)],
                defaults={
                    "tenant": tenant,
                    "feedback_type": FeedbackType.DOWNVOTE,
                },
            )
            feedback_count += 1

        return feedback_count

    def _seed_ingestion_runs(self, tenant: Tenant) -> int:
        run_specs = [
            {
                "plugin_name": SourcePluginName.RSS,
                "status": RunStatus.SUCCESS,
                "items_fetched": 92,
                "items_ingested": 57,
                "error_message": "",
                "started_hours_ago": 6,
                "duration_minutes": 14,
            },
            {
                "plugin_name": SourcePluginName.REDDIT,
                "status": RunStatus.SUCCESS,
                "items_fetched": 28,
                "items_ingested": 18,
                "error_message": "",
                "started_hours_ago": 4,
                "duration_minutes": 6,
            },
            {
                "plugin_name": SourcePluginName.RSS,
                "status": RunStatus.FAILED,
                "items_fetched": 0,
                "items_ingested": 0,
                "error_message": "Timed out while polling one disabled feed mirror.",
                "started_hours_ago": 30,
                "duration_minutes": 5,
            },
            {
                "plugin_name": SourcePluginName.REDDIT,
                "status": RunStatus.SUCCESS,
                "items_fetched": 24,
                "items_ingested": 16,
                "error_message": "",
                "started_hours_ago": 32,
                "duration_minutes": 7,
            },
            {
                "plugin_name": SourcePluginName.RSS,
                "status": RunStatus.SUCCESS,
                "items_fetched": 88,
                "items_ingested": 54,
                "error_message": "",
                "started_hours_ago": 54,
                "duration_minutes": 13,
            },
            {
                "plugin_name": SourcePluginName.REDDIT,
                "status": RunStatus.FAILED,
                "items_fetched": 0,
                "items_ingested": 0,
                "error_message": "Community listing temporarily unavailable during sync.",
                "started_hours_ago": 80,
                "duration_minutes": 4,
            },
        ]
        now = timezone.now()
        for spec in run_specs:
            started_hours_ago = cast(int, spec["started_hours_ago"])
            duration_minutes = cast(int, spec["duration_minutes"])
            run = IngestionRun.objects.create(
                tenant=tenant,
                plugin_name=cast(str, spec["plugin_name"]),
                status=cast(str, spec["status"]),
                items_fetched=cast(int, spec["items_fetched"]),
                items_ingested=cast(int, spec["items_ingested"]),
                error_message=cast(str, spec["error_message"]),
            )
            run.started_at = now - timedelta(hours=started_hours_ago)
            run.completed_at = run.started_at + timedelta(minutes=duration_minutes)
            run.save(update_fields=["started_at", "completed_at"])
        return len(run_specs)

    def _sync_embeddings(self, contents: list[Content]) -> int:
        embedded_count = 0
        for content in sorted(contents, key=lambda item: item.id):
            try:
                upsert_content_embedding(content)
            except (HTTPError, ResponseHandlingException) as exc:
                self.stderr.write(
                    self.style.WARNING(
                        "Skipping remaining embedding sync because the embedding or "
                        f"vector service is unavailable: {exc}"
                    )
                )
                break
            embedded_count += 1
        return embedded_count

    def _build_reference_articles(self) -> list[dict[str, Any]]:
        articles = list(LEGACY_REFERENCE_ARTICLES)
        for round_index in range(5):
            for topic_index, topic in enumerate(REFERENCE_TOPICS):
                articles.append(
                    {
                        "url": f"https://example.com/reference/{topic['slug']}-{round_index + 1}",
                        "title": topic["title"],
                        "author": "Reference Corpus",
                        "content_text": topic["content"],
                        "days_ago": 32 + round_index * 7 + topic_index,
                    }
                )
        return articles

    def _build_demo_content(self) -> list[dict[str, Any]]:
        articles = list(LEGACY_SAMPLE_CONTENT)
        articles.extend(self._build_generated_rss_content())
        articles.extend(self._build_generated_reddit_content())
        return articles

    def _build_generated_rss_content(self) -> list[dict[str, Any]]:
        articles = []
        for index in range(147):
            band = self._band_for_index(index, relevant_cutoff=87, borderline_cutoff=122)
            publication = RSS_PUBLICATIONS[index % len(RSS_PUBLICATIONS)]
            topic = RSS_TOPIC_BLUEPRINTS[index % len(RSS_TOPIC_BLUEPRINTS)]
            relevance_score = self._relevance_score(index, band)
            articles.append(
                {
                    "url": (
                        f"https://{publication['host']}/2026/04/"
                        f"{topic['slug']}-{index + 1:03d}"
                    ),
                    "title": self._rss_title(publication["label"], topic["headline"], band),
                    "author": f"{publication['label']} Editorial",
                    "source_plugin": SourcePluginName.RSS,
                    "content_text": self._rss_body(publication["label"], topic["body"], band),
                    "days_ago": 1 + (index % 30),
                    "content_type": self._content_type_for_band(topic["content_type"], band),
                    "classification_confidence": self._classification_confidence(index),
                    "relevance_score": relevance_score,
                    "entity_name": publication["entity_name"],
                    "used_llm": band == "borderline",
                }
            )
        return articles

    def _build_generated_reddit_content(self) -> list[dict[str, Any]]:
        articles = []
        for index in range(49):
            band = self._band_for_index(index, relevant_cutoff=24, borderline_cutoff=34)
            subreddit = REDDIT_COMMUNITIES[index % len(REDDIT_COMMUNITIES)]
            topic = REDDIT_TOPIC_BLUEPRINTS[index % len(REDDIT_TOPIC_BLUEPRINTS)]
            articles.append(
                {
                    "url": (
                        f"https://www.reddit.com/r/{subreddit}/comments/"
                        f"demo{index + 1:03d}/{topic['slug']}/"
                    ),
                    "title": self._reddit_title(subreddit, topic["headline"], band),
                    "author": f"u/demo_{subreddit}_{index + 1:03d}",
                    "source_plugin": SourcePluginName.REDDIT,
                    "content_text": self._reddit_body(subreddit, topic["body"], band, index),
                    "days_ago": 1 + ((index * 2) % 30),
                    "content_type": self._content_type_for_band(topic["content_type"], band),
                    "classification_confidence": self._classification_confidence(index + 200),
                    "relevance_score": self._relevance_score(index + 200, band),
                    "entity_name": None,
                    "used_llm": band == "borderline",
                }
            )
        return articles

    @staticmethod
    def _band_for_index(index: int, *, relevant_cutoff: int, borderline_cutoff: int) -> str:
        if index < relevant_cutoff:
            return "relevant"
        if index < borderline_cutoff:
            return "borderline"
        return "irrelevant"

    @staticmethod
    def _classification_confidence(index: int) -> float:
        if index % 11 == 0:
            return 0.55
        return round(0.66 + (index % 8) * 0.03, 2)

    @staticmethod
    def _relevance_score(index: int, band: str) -> float:
        if band == "relevant":
            return round(0.74 + (index % 18) * 0.012, 2)
        if band == "borderline":
            return round(0.44 + (index % 15) * 0.015, 2)
        return round(0.12 + (index % 12) * 0.015, 2)

    @staticmethod
    def _content_type_for_band(base_content_type: str, band: str) -> str:
        if band == "irrelevant" and base_content_type == "technical_article":
            return "other"
        return base_content_type

    @staticmethod
    def _rss_title(source_label: str, headline: str, band: str) -> str:
        if band == "relevant":
            return f"{headline}"
        if band == "borderline":
            return f"{headline} for teams still shaping their platform charter"
        return f"{source_label}: {headline.lower().capitalize()} outside the core platform loop"

    @staticmethod
    def _reddit_title(subreddit: str, headline: str, band: str) -> str:
        if band == "relevant":
            return f"r/{subreddit}: {headline}"
        if band == "borderline":
            return f"r/{subreddit}: {headline} and where teams disagree"
        return f"r/{subreddit}: {headline} with limited editorial fit"

    @staticmethod
    def _rss_body(source_label: str, body: str, band: str) -> str:
        if band == "relevant":
            return (
                f"{source_label} reports a concrete platform engineering practice. "
                f"{body} The example is directly applicable to infrastructure, "
                "developer experience, and reliability workflows."
            )
        if band == "borderline":
            return (
                f"{source_label} touches on a topic adjacent to platform engineering. "
                f"{body} Editors would probably want to review whether the angle is "
                "specific enough for the newsletter audience."
            )
        return (
            f"{source_label} covers a topic that only partially overlaps with the "
            f"newsletter focus. {body} It is still technical, but the connection to "
            "platform engineering is weak compared with stronger candidates."
        )

    @staticmethod
    def _reddit_body(subreddit: str, body: str, band: str, index: int) -> str:
        score = 18 + (index % 35)
        if band == "relevant":
            return (
                f"A discussion in r/{subreddit} highlights platform operations trade-offs. "
                f"{body} The post picked up roughly {score} upvotes and several replies "
                "from practitioners sharing first-hand implementation details."
            )
        if band == "borderline":
            return (
                f"A thread in r/{subreddit} raises a useful but mixed operational question. "
                f"{body} The discussion is practical, yet it needs editorial judgment to "
                "decide whether it is specific enough for platform readers."
            )
        return (
            f"A thread in r/{subreddit} is only loosely connected to the tenant topic. "
            f"{body} The conversation is interesting, but it is more peripheral than the "
            "other seeded stories."
        )

    @staticmethod
    def _review_reason_for_article(
        classification_confidence: float,
        relevance_score: float,
    ) -> str | None:
        if classification_confidence < settings.AI_CLASSIFICATION_REVIEW_THRESHOLD:
            return ReviewReason.LOW_CONFIDENCE_CLASSIFICATION
        if relevance_score < settings.AI_RELEVANCE_SUMMARIZE_THRESHOLD and (
            relevance_score >= settings.AI_RELEVANCE_REVIEW_THRESHOLD
        ):
            return ReviewReason.BORDERLINE_RELEVANCE
        return None

    @staticmethod
    def _classification_explanation(article: dict[str, Any]) -> str:
        return (
            f"The seeded classifier maps this item to {article['content_type']} based "
            "on its language, operating context, and editorial angle."
        )

    @staticmethod
    def _relevance_explanation(article: dict[str, Any]) -> str:
        relevance_score = float(article["relevance_score"])
        if article.get("used_llm", False):
            return (
                f"Borderline similarity of {relevance_score:.2f} required editorial "
                "adjudication, so the seeded result keeps this item in the review band."
            )
        if relevance_score >= settings.AI_RELEVANCE_SUMMARIZE_THRESHOLD:
            return (
                f"Reference corpus similarity is strong at {relevance_score:.2f}, so the "
                "item is ready to surface without additional review."
            )
        return (
            f"Reference corpus similarity is weak at {relevance_score:.2f}, so the "
            "seed marks the item as archived rather than surfaced."
        )

    @staticmethod
    def _relevance_model_used(article: dict[str, Any]) -> str:
        if article.get("used_llm", False):
            return settings.AI_RELEVANCE_MODEL
        return f"embedding:{settings.EMBEDDING_MODEL}"

    @staticmethod
    def _summary_for_article(article: dict[str, Any]) -> str:
        source_name = article["source_plugin"].upper()
        return (
            f"{article['title']} gives platform teams a concrete angle on delivery, "
            f"reliability, or developer experience. The seeded summary keeps the focus "
            f"on why this {source_name} item is worth surfacing in the newsletter."
        )
