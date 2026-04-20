# Newsletter Maker

An AI-powered content curation platform for technically-oriented newsletters. Newsletter Maker ingests content from dozens of sources, builds authority models of people and companies in a domain, and surfaces the most relevant articles, trends, and themes for each edition — so editors spend their time writing, not searching.

The system is multi-tenant: each newsletter has its own tracked entities, relevance model, and content pipeline. Designed for non-technical editors who don't know what a vector database is and don't need to.

## What This Does That Existing Tools Don't

Tools like Feedly, UpContent, and ContentStudio handle parts of the content curation problem. Newsletter Maker combines several capabilities none of them offer:

- **Authority scoring from newsletter cross-referencing.** By ingesting peer newsletters, the system builds an authority model based on who real editors actually link to — a human-curated endorsement signal no existing tool provides.
- **Per-editor relevance training.** Upvote/downvote feedback trains a personalized relevance model per tenant. The tool learns what *you* consider valuable.
- **Unified entity model.** A person's blog, LinkedIn, Bluesky, GitHub, and conference talks are linked into a single profile with an authority score — a holistic view of who matters in a space.
- **Competitive intelligence.** "These 3 peer newsletters all covered topic X this week, but you haven't." A natural output of newsletter ingestion that no curation tool provides.
- **Historical trend analysis.** Not just what's trending now, but trajectories over weeks. Content is retained indefinitely for long-term pattern detection.

## Architecture Highlights

### Composable AI Skills

Every AI capability is a standalone, documented module following the Claude Skills progressive disclosure format:

1. **Metadata layer** — name and trigger description (all the orchestrator sees during routing)
2. **Instructions layer** — the full standard operating procedure for the task
3. **Resources layer** — deterministic scripts, reference data, and templates

Seven skills form the core pipeline: Content Classification, Relevance Scoring, Deduplication, Summarization, Theme Detection, Newsletter Email Extraction, and Entity Extraction. Each has a defined input/output schema and is independently invocable — from the pipeline, from the UI, or chained into user-defined workflows.

The skill format is model-agnostic. The same skill definitions work with Claude, GPT, and local models via Ollama. The model is a configuration parameter, not a hardcoded dependency.

### LangGraph Orchestration

Skills are composed into workflows by LangGraph, which provides what skills alone can't: deterministic routing, state persistence, conditional edges, and human-in-the-loop checkpoints. If the ingestion pipeline fails at step 3 of 5, it resumes from that checkpoint rather than reprocessing from scratch.

The orchestrator handles multi-model routing — each skill uses a model chosen for the task (Qwen for structured extraction and dev-time grounding, Gemma for clean summarization prose, DeepSeek for cross-document reasoning, Command R+ for production RAG scoring). During development, all models are accessed via OpenRouter as a unified API gateway at ~$2.30/month. In production, every selected model is self-hostable via Ollama for zero marginal LLM cost.

### Non-Technical User Composability

Skills are exposed as actions throughout the UI. When viewing any content item, editors can invoke skills directly — summarize an article, extract entities, explain a relevance score — without understanding the underlying pipeline. Results render inline with copy, regenerate, and follow-up actions.

The roadmap progresses from contextual actions (MVP) to multi-step skill chaining (user picks a sequence, output feeds forward) to saved workflow templates that editors can re-run with one click.

### Plugin Architecture for Data Sources

Each data source implements a common interface (`fetch_new_content`, `get_entity_profile`, `health_check`) and handles its own auth and rate limiting. The core system just calls the interface. Planned integrations:

| Source | Purpose | Priority |
| ------ | ------- | -------- |
| RSS | Blog/site tracking for followed entities | Phase 1 |
| Reddit | Trend detection and community sentiment | Phase 1 |
| Resend Inbound | Newsletter email ingestion and authority signals | Phase 2 |
| Bluesky | Entity content tracking (open AT Protocol) | Phase 2 |
| Mastodon | Entity content tracking (ActivityPub) | Phase 3 |
| LinkedIn | Entity enrichment and article discovery | Phase 4 |

### Production-Grade Error Handling

The system is designed for graceful failure, not silent corruption. Unparseable newsletters, ambiguous entity matches, and low-confidence classifications are flagged for human review via a dedicated queue in the UI. Skills return structured error responses. LangGraph nodes implement circuit breakers and max-loop limits. Every skill invocation is logged with model used, latency, confidence, and success/failure status.

## Tech Stack

**Backend:** Django + DRF · Celery + Redis · PostgreSQL · Qdrant (vector DB)

**AI Pipeline:** LangGraph · Claude Skills format · Multi-model via OpenRouter (Llama 3.1, Gemma 3, DeepSeek V3, Qwen 2.5; Command R+ for production) · Ollama for self-hosting · Sentence embeddings

**Frontend:** React · Designed for non-technical editors

**Deployment:** Docker Compose (MVP) · Kubernetes-ready · 12-factor configuration

## Implementation Plan

| Phase | Focus | Key Deliverables |
| ----- | ----- | ---------------- |
| **1. MVP** | Content ingestion + basic surfacing | RSS and Reddit plugins · Entity model in Postgres · Qdrant for embeddings · Classification, relevance scoring, and summarization skills · Dashboard with upvote/downvote · Seed script for demo data |
| **2. Authority** | Newsletter ingestion + authority signals | Resend email intake with LLM extraction · Subscription confirmation flow · Authority scoring from mention frequency · Bluesky plugin · Deduplication and entity extraction skills |
| **3. Intelligence** | Expanded sources + trend analysis | Mastodon plugin · Trend velocity detection · Theme suggestions · Source diversity analysis · Original content idea generation |
| **4. Polish** | Advanced features | LinkedIn integration · Automated entity discovery · Full multi-signal authority model · Newsletter draft generation |

## Project Documentation

## Local Development

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

1. Run `just dev` to build the Django image and start Django, Celery, Postgres, Redis, Qdrant, and Nginx. If `.env` is missing, the `just` command copies `.env.example` automatically.
2. Update `.env` with non-default secrets before using the stack outside local development. The example file uses SQLite and localhost URLs so host-side `manage.py` commands work even without Docker.
3. Open `http://localhost:8080/healthz/` for a liveness check and `http://localhost:8080/admin/` for Django admin.

For host-based development without Docker, install `requirements.txt`, then use `python3 manage.py migrate` and `python3 manage.py runserver`. The default `.env.example` is host-safe; Docker Compose overrides the service URLs inside containers.

When `just dev` is running, Django admin uses the Postgres database inside Docker, not the host SQLite database. That means host commands like `python manage.py createsuperuser` create users in SQLite and will not let you log into the Docker-backed admin site.

Create or update an admin user for the running Docker stack with:

```bash
just createsuperuser
just changepassword your-username
```

For the default local bootstrap, `.env` also seeds an `admin` superuser in the container database using `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, and `DJANGO_SUPERUSER_PASSWORD`.

- [PLANNING.md](docs/PLANNING.md) — Full architecture decisions, data model, and feedback loop design
- [VENDOR.md](docs/VENDOR.md) — Per-skill model selection, rationale, and API pricing
- [GENRES.md](docs/GENRES.md) — Newsletter format types and layout templates
- [IMPLEMENTATION.md](docs/IMPLEMENTATION.md) — Additional implementation notes
