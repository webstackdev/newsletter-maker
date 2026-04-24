# Implementation Notes

## Phase 1: MVP — Content Ingestion + Basic Surfacing

**Goal:** Ingest content from RSS and Reddit, run it through a classification → relevance → summarization pipeline, and surface the most relevant items in a dashboard where editors can upvote/downvote content.

### Work Packages

Phase 1 is organized into seven work packages that build on each other. Each produces a testable, runnable increment.

---

### WP1: Project Scaffold + Docker Compose

Set up the Django project, Docker infrastructure, and development environment.

**Deliverables:**

- Django project (`newsletter_maker/`) with DRF installed
- `docker-compose.yml` with all services:

  | Service | Image | Purpose |
  |---------|-------|---------|
  | `django` | Custom Dockerfile (gunicorn) | API server |
  | `celery-worker` | Same image, different entrypoint | Background task execution |
  | `celery-beat` | Same image, different entrypoint | Scheduled task triggers |
  | `postgres` | `postgres:16` | Relational data |
  | `redis` | `redis:7-alpine` | Celery broker + cache |
  | `qdrant` | `qdrant/qdrant:latest` | Vector storage |
  | `nginx` | `nginx:alpine` | Reverse proxy |

- `.env.example` with all required environment variables:
  - `DATABASE_URL`, `REDIS_URL`, `QDRANT_URL`
  - `OPENROUTER_API_KEY`
    - `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`
    - `OLLAMA_URL` for local Ollama embeddings
    - `OPENROUTER_API_BASE` for hosted OpenAI-compatible embeddings APIs
  - `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`
- Health check endpoints: `GET /healthz/` (system health), `GET /readyz/` (DB + Qdrant reachable)
- `justfile` with commands: `dev` (docker compose up), `test`, `migrate`, `seed`, `shell`
- `structlog` configured for JSON logging to stdout

**Definition of done:** `just dev` brings up all services, `/healthz/` returns 200, Django admin is accessible.

### WP2: Data Models

Core Django models for multi-tenant content management.

**Models:**

```python
class Tenant(models.Model):
    name = models.CharField(max_length=255)             # Newsletter name
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    topic_description = models.TextField()              # "Platform engineering and DevOps"
    content_retention_days = models.IntegerField(default=365)
    created_at = models.DateTimeField(auto_now_add=True)

class TenantConfig(models.Model):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE)
    upvote_authority_weight = models.FloatField(default=0.1)
    downvote_authority_weight = models.FloatField(default=-0.05)
    authority_decay_rate = models.FloatField(default=0.95)  # Monthly multiplier

class Entity(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    type = models.CharField(choices=ENTITY_TYPE_CHOICES)  # individual, vendor, organization
    description = models.TextField(blank=True)
    authority_score = models.FloatField(default=0.5)
    website_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    bluesky_handle = models.CharField(max_length=255, blank=True)
    mastodon_handle = models.CharField(max_length=255, blank=True)
    twitter_handle = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('tenant', 'name')

class Content(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    url = models.URLField()
    title = models.CharField(max_length=512)
    author = models.CharField(max_length=255, blank=True)
    entity = models.ForeignKey(Entity, null=True, blank=True, on_delete=models.SET_NULL)
    source_plugin = models.CharField(max_length=64)     # "rss", "reddit"
    content_type = models.CharField(max_length=64, blank=True)  # Set by Classification skill
    published_date = models.DateTimeField()
    ingested_at = models.DateTimeField(auto_now_add=True)
    content_text = models.TextField()
    relevance_score = models.FloatField(null=True)
    is_active = models.BooleanField(default=True)       # Soft delete for retention

    class Meta:
        indexes = [
            models.Index(fields=['tenant', '-published_date']),
            models.Index(fields=['tenant', '-relevance_score']),
            models.Index(fields=['url']),               # Dedup on ingest
        ]

class SkillResult(models.Model):
    content = models.ForeignKey(Content, on_delete=models.CASCADE, related_name='skill_results')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    skill_name = models.CharField(max_length=64)
    status = models.CharField(choices=STATUS_CHOICES)    # pending, running, completed, failed
    result_data = models.JSONField(null=True)
    error_message = models.TextField(blank=True)
    model_used = models.CharField(max_length=64)
    latency_ms = models.IntegerField(null=True)
    confidence = models.FloatField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    superseded_by = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        indexes = [
            models.Index(fields=['content', 'skill_name']),
            models.Index(fields=['tenant', 'created_at']),
        ]

class UserFeedback(models.Model):
    content = models.ForeignKey(Content, on_delete=models.CASCADE)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    feedback_type = models.CharField(choices=[('upvote', 'Upvote'), ('downvote', 'Downvote')])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('content', 'user')  # One vote per user per item

class IngestionRun(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    plugin_name = models.CharField(max_length=64)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True)
    status = models.CharField(choices=RUN_STATUS_CHOICES) # running, success, failed
    items_fetched = models.IntegerField(default=0)
    items_ingested = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'plugin_name', '-started_at']),
        ]

class ReviewQueue(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    content = models.ForeignKey(Content, on_delete=models.CASCADE)
    reason = models.CharField(max_length=64)             # low_confidence_classification, borderline_relevance
    confidence = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    resolution = models.CharField(max_length=64, blank=True)  # human_approved, human_rejected
```

**DRF serializers and viewsets** for all models, scoped by `request.user`'s tenant.

**Definition of done:** Models migrated, Django admin registered, API endpoints return JSON for all models, tenant scoping enforced.

### WP3: Data Source Plugins (RSS + Reddit)

Implement the plugin interface and the two Phase 1 plugins.

**Plugin interface:**

```python
class SourcePlugin(ABC):
    @abstractmethod
    def fetch_new_content(self, since: datetime) -> list[ContentItem]: ...

    @abstractmethod
    def health_check(self) -> bool: ...
```

**RSS plugin:**

- Uses `feedparser` to fetch configured feed URLs
- Stores seen entry GUIDs to avoid re-ingesting duplicates
- Extracts: URL, title, author, published date, summary/excerpt
- Links to Entity if feed URL matches a tracked entity's website
- Scheduled via Celery Beat: every 6 hours

**Reddit plugin:**

- Uses PRAW (Python Reddit API Wrapper)
- Monitors configured subreddits via `.new()` and `.hot()`
- Extracts: title, selftext, URL, score, subreddit, author
- Tracks upvote count as a quality signal
- Does **not** link Reddit users to Entity profiles
- Scheduled via Celery Beat: every 6 hours

**Plugin configuration** stored in a `SourceConfig` model:

```python
class SourceConfig(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    plugin_name = models.CharField(max_length=64)    # "rss", "reddit"
    config = models.JSONField()                      # Plugin-specific: {"feed_url": "..."} or {"subreddit": "..."}
    is_active = models.BooleanField(default=True)
    last_fetched_at = models.DateTimeField(null=True)
```

**Celery tasks:**

- `run_ingestion(tenant_id, plugin_name)` — fetches new content, creates `Content` records, logs `IngestionRun`
- `run_all_ingestions()` — Beat-scheduled task that triggers ingestion for all active source configs

**Natural next steps:**

- Add a small management command or just target to trigger run_all_ingestions and run_ingestion manually during development.
- Add source health reporting so /admin/health or a tenant API endpoint can surface RSS/Reddit plugin status from health_check().
- Tighten the ingestion contract by storing plugin-specific metadata such as Reddit score/subreddit or RSS entry IDs if you want better deduplication and debugging.

**Definition of done:** RSS plugin ingests from a real feed. Reddit plugin ingests from a real subreddit. `IngestionRun` records log success/failure. Health checks return correct status.

What is not built yet is the full done state from the plan, especially live feed/subreddit wiring in a running stack, source-health UI/endpoints, and richer ingestion metadata/dedup strategy.

### WP4: Embeddings + Qdrant Integration

Compute embeddings for all ingested content and store them in Qdrant for similarity search.

**Embedding backend:** Configurable via `EMBEDDING_PROVIDER` plus `EMBEDDING_MODEL`.

- `sentence-transformers`: local Hugging Face / SentenceTransformers model loading
- `ollama`: local model served over Ollama's embedding API
- `openrouter`: hosted embeddings through the OpenRouter `/embeddings` API

Examples:

- `EMBEDDING_PROVIDER=sentence-transformers`, `EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2`
- `EMBEDDING_PROVIDER=ollama`, `EMBEDDING_MODEL=nomic-embed-text`
- `EMBEDDING_PROVIDER=ollama`, `EMBEDDING_MODEL=qwen3-embedding-8b`
- `EMBEDDING_PROVIDER=openrouter`, `EMBEDDING_MODEL=openai/text-embedding-3-small`

**Qdrant setup:**

- One collection per tenant (named `tenant_{id}_content`)
- HNSW index for fast similarity search
- Each point stores: vector, plus payload metadata (content ID, URL, title, published date, source plugin)

**Integration flow:**

1. Plugin fetches article → `Content` record created in Postgres
2. Post-save signal (or inline in ingestion task) computes embedding
3. The configured embedding provider returns a vector for the content text
4. Embedding + metadata upserted into tenant's Qdrant collection
5. `Content.embedding_id` stores the Qdrant point ID for later retrieval

**Reference corpus seeding:**

- Each tenant's Qdrant collection is initialized with embeddings from reference articles that define "what's relevant" for this newsletter
- Seed script pre-populates with ~50-100 sample articles per tenant
- These reference embeddings serve as the relevance baseline for the scoring skill

**Utility functions:**

- `embed_text(text: str) -> list[float]` — compute embedding for a text string
- `upsert_content_embedding(content: Content)` — embed and store in Qdrant
- `search_similar(tenant_id: int, query_vector: list[float], limit: int) -> list[ScoredPoint]` — find similar content
- `get_reference_similarity(tenant_id: int, vector: list[float]) -> float` — average similarity against reference corpus

**Operational usage:**

- `just embed-all` — backfill embeddings for all content rows
- `just embed-tenant <tenant_id>` — backfill one tenant's content
- `python3 manage.py sync_embeddings --content-id <id>` — re-embed one record

**Definition of done:** Every ingested content item has an embedding in Qdrant. `search_similar` returns semantically related articles. Reference corpus is seeded for test tenant.

- Run `just embed-smoke` to confirm Django can talk to Ollama.
- If that works, run `just embed-all` or `just embed-tenant <tenant_id>` to backfill real content.

Natural next steps:

- add a DRF endpoint or admin action that returns similar content for a given item using search_similar_content
- expand the seeded reference corpus from the current minimal set into a more realistic tenant baseline
- wire WP5 relevance scoring to get_reference_similarity and the seeded reference items

### WP5: AI Skills + LangGraph Pipeline

Implement the three Phase 1 skills and wire them into a LangGraph orchestrator.

**Skill format:** Each skill lives in a `skills/{skill_name}/` directory following Claude-style progressive disclosure:

```bash
skills/
├── content_classification/
│   ├── SKILL.md          # YAML frontmatter (Level 1) + SOP instructions (Level 2)
│   └── references/       # Category definitions, examples (Level 3)
├── relevance_scoring/
│   ├── SKILL.md
│   └── references/       # Scoring rubric, example judgments
└── summarization/
    ├── SKILL.md
    └── references/       # Style guide, example summaries
```

**Skill implementations (Python wrappers around the prompt + model call):**

**1. Content Classification** (Llama 3.1 70B via OpenRouter)

- Input: `{title, content_text, url}`
- Output: `{content_type: str, confidence: float}`
- Categories: technical_article, tutorial, opinion, product_announcement, event, release_notes, other
- If `confidence < 0.6`: add to `ReviewQueue` with reason `low_confidence_classification`

**2. Relevance Scoring** (Embeddings primary, Qwen 2.5 72B for borderline)

- Input: `{content_embedding, tenant_id}`
- Step 1: Compute cosine similarity against tenant's reference corpus in Qdrant
- Step 2: If similarity > 0.85 → score = similarity (no LLM call). If similarity < 0.5 → score = similarity (no LLM call). If 0.5 - 0.85 → call Qwen for nuanced judgment with explanation.
- Output: `{relevance_score: float, explanation: str, used_llm: bool}`
- If `0.4 < relevance_score < 0.7`: add to `ReviewQueue` with reason `borderline_relevance`

**3. Summarization** (Gemma 3 27B via OpenRouter)

- Input: `{title, content_text, newsletter_topic}`
- Output: `{summary: str}` (2-3 sentences, newsletter-ready)
- Only runs on content with `relevance_score >= 0.7`

**LangGraph pipeline:**

```python
from langgraph.graph import StateGraph, END

class PipelineState(TypedDict):
    content_id: int
    tenant_id: int
    classification: dict | None
    relevance: dict | None
    summary: dict | None
    status: str  # "processing", "completed", "archived", "review"

def build_ingestion_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("classify", classify_node)
    graph.add_node("score_relevance", relevance_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("archive", archive_node)
    graph.add_node("queue_review", queue_review_node)

    graph.set_entry_point("classify")
    graph.add_edge("classify", "score_relevance")
    graph.add_conditional_edges("score_relevance", route_by_relevance, {
        "relevant": "summarize",
        "borderline": "queue_review",
        "irrelevant": "archive",
    })
    graph.add_edge("summarize", END)
    graph.add_edge("archive", END)
    graph.add_edge("queue_review", END)

    return graph.compile(checkpointer=redis_checkpointer)
```

**Routing logic:**

- `relevance_score >= 0.7` → summarize → surface in dashboard
- `0.4 <= relevance_score < 0.7` → queue for human review (surfaced with "Low confidence" flag)
- `relevance_score < 0.4` → archive (soft-delete, `is_active = False`)

**Error handling:**

- Each node wrapped in try/except; failures logged as `SkillResult` with `status=failed`
- Max 2 retries per node before marking as failed and moving to review queue
- Circuit breaker: after 5 consecutive failures on a skill, pause pipeline and alert via log

**Celery integration:**

- `process_content(content_id)` — Celery task that runs the LangGraph pipeline for one content item
- Called automatically after ingestion creates a new `Content` record
- State checkpointed in Redis — if worker dies mid-pipeline, resumes from last completed node

**Definition of done:** New content ingested via RSS/Reddit automatically flows through classify → score → summarize. Results persisted as `SkillResult` records. Borderline items appear in review queue. Irrelevant items archived.

---

### WP6: React Frontend (Minimal Dashboard)

A focused UI for reviewing and acting on surfaced content.

**Pages:**

1. **Content Dashboard** (`/`)
   - List of surfaced content for current period, sorted by relevance score
   - Each item shows: title, source, published date, relevance score, content type badge
   - Upvote/downvote buttons on each item
   - Click to expand → full detail view with skill action bar
   - Filter by: content type, date range, source plugin
   - "Pending review" tab showing items from the review queue

2. **Content Detail** (expanded view or `/content/{id}`)
   - Full article metadata
   - `<SkillActionBar>` component with buttons:
     - **Summarize** — triggers summarization skill, shows result inline
     - **Explain Relevance** — triggers relevance scoring skill, shows score + explanation
     - **Find Related** — queries Qdrant for similar embeddings, shows related articles
   - Each skill result renders in a collapsible section with Copy and Regenerate actions
   - Persisted results shown immediately if already generated; "Regenerate" creates a new result

3. **Entity Management** (`/entities`)
   - CRUD for entities (name, type, description, platform handles)
   - Simple form — no automated discovery or linking in Phase 1

4. **Ingestion Health** (`/admin/health`)
   - Status of each data source plugin: last fetch, items count, error status
   - Color-coded: green (healthy), yellow (degraded), red (failing)

5. **Source Configuration** (`/admin/sources`)
   - Add/edit/disable RSS feeds and Reddit subreddits
   - Per-source health status

**API integration:**

- All data fetched via DRF endpoints
- Skill invocations: `POST /api/v1/tenants/{tenant_id}/contents/{id}/skills/{skill_name}/`
  - Returns `202 Accepted` for async skills (summarization)
    - Frontend polls `GET /api/v1/tenants/{tenant_id}/skill-results/{id}/` until `status=completed`
  - Returns `200` with result for fast skills (find related via Qdrant)
- Feedback: `POST /api/v1/tenants/{tenant_id}/feedback/` with `{content: <id>, feedback_type: "upvote"|"downvote"}`

**Definition of done:** User can view dashboard, expand articles, trigger skills, see results inline, upvote/downvote content, manage entities and sources.

---

### WP7: Seed Script + Demo Data

Make the project immediately demo-able without weeks of data accumulation.

**`just seed` command runs a management command that:**

1. Creates a demo tenant ("Platform Engineering Weekly") with topic description
2. Creates ~15 entities:
   - 8 individuals (Kelsey Hightower, Charity Majors, etc.)
   - 5 vendors (HashiCorp, Datadog, Grafana Labs, etc.)
   - 2 organizations (CNCF, Linux Foundation)
3. Creates ~200 content items spanning 30 days:
   - ~150 from RSS (mix of relevant and irrelevant)
   - ~50 from Reddit (r/kubernetes, r/devops posts with realistic scores)
4. Embeds all content and seeds Qdrant with reference corpus (~50 curated articles)
5. Runs the LangGraph pipeline on all content to populate:
   - Classification results
   - Relevance scores
   - Summaries for relevant items
   - Review queue entries for borderline items
6. Adds sample user feedback (~30 upvotes, ~15 downvotes) to demonstrate feedback state
7. Creates sample `IngestionRun` records showing healthy ingestion history

**Definition of done:** `just seed` produces a fully populated dashboard with realistic data, scored and summarized content, and a non-empty review queue. A new user can explore the full UI immediately.

---

### Work Package Dependencies

```bash
WP1 (Scaffold)
 └─► WP2 (Models)
      ├─► WP3 (Plugins)
      │    └─► WP4 (Embeddings)
      │         └─► WP5 (Skills + Pipeline)
      │              └─► WP7 (Seed Script)
      └─► WP6 (Frontend)
           └─► WP7 (Seed Script)
```

WP6 (Frontend) can begin in parallel with WP3-WP5 once models and API endpoints exist — it can develop against mock data initially and integrate with real endpoints as they land.

---

### Phase 1 Cost Summary

| Category | Monthly Cost |
|----------|-------------|
| VPS hosting (4GB+ RAM) | ~$30 |
| OpenRouter LLM calls (1 tenant, ~2K articles) | ~$2.30 |
| Embeddings (local) | $0 |
| Qdrant (self-hosted) | $0 |
| PostgreSQL + Redis (self-hosted) | $0 |
| **Total** | **~$32/month** |

### What's Explicitly Out of Scope

- Newsletter email ingestion (Resend) → Phase 2
- Bluesky / Mastodon / LinkedIn plugins → Phase 2+
- Deduplication skill → Phase 2
- Entity extraction skill → Phase 2
- Theme detection skill → Phase 3
- Authority scoring in relevance ranking → Phase 2 (scores exist but aren't used in ranking yet)
- Topic centroid feedback loop → Phase 2
- Few-shot training from feedback → Phase 3
- Multi-step skill chaining UI → Phase 3
- Saved workflow templates → Phase 4
- Prometheus / Grafana / external observability → Phase 3+
- Kubernetes deployment → Phase 2+
- CI/CD beyond basic GitHub Actions → Phase 2+
