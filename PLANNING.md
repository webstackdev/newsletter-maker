# Planning Discussion

## Project Goals

Help curate content for regular technically-oriented newsletters. The tool is multi-tenant — it supports multiple newsletters on different topics, maintained by different users. This lays the groundwork for potential SaaS use or adoption by a team at a newsletter company where different editors maintain different newsletters.

The UI must be designed for non-technical end users. This is a product, not a developer tool.

**Composability is the core philosophy.** Every capability in the system is a self-contained unit with clean inputs/outputs that can be invoked independently or chained together. The plugin architecture already points this direction, but the AI pipeline itself needs to be decomposed into composable units too — not just a monolithic LangGraph DAG.

**Model-agnostic Skills, not vendor lock-in.** The architecture uses Claude-style Skills as the module format — each AI capability (content classification, summarization, relevance scoring, entity extraction) is a standalone, documented "Skill" with a clear interface that a non-technical user could understand and invoke. However, the Skills format is model-agnostic: GPT models can consume Claude Skills directly, and local models via Ollama may be able to as well. This lets us use the right model for each task — Claude Sonnet for high-value generation, cheaper/local models for commodity tasks — without changing the Skill definitions.

**Non-technical users are half the job.** The UI needs to be polished, intuitive, and designed for editors who don't know what a vector database is. But beyond the UI, the system design itself should be legible — a non-technical person should be able to understand what the system does by reading the skill/tool descriptions.

**Production agents, not demos.** The background ingestion pipeline needs proper error handling, retry logic, health monitoring, and clear escalation paths (e.g., "this newsletter email couldn't be parsed, flagging for human review" rather than silently failing).

**Systems of record integration.** The plugin architecture allows easy integration with HubSpot, Google Drive, and Slack.

### What the Tool Should Do

- Surface the most important articles, events, and ideas relevant to a newsletter's topic since its last edition was published
- Suggest themes and ideas for original content (e.g. "Our Insight" segments, blog articles)
- Over time, build and maintain a database of people, companies, and organizations worth tracking
- Ingest new content from those entities and make sense of it for the newsletter writer
- Let users give feedback (upvote/downvote) on surfaced content and entities to train the relevance model over time

### Hard Problems

- **Content deduplication:** The same announcement gets covered by 15 blogs. The tool should recognize that and surface the best version, not all 15.
- **Trend velocity:** Not just "what exists" but "what is gaining traction *right now*" — a signal that matters for weekly publishing cadence.
- **Source diversity:** A good newsletter doesn't link to the same 3 sites every week. The tool should help balance sources.
- **Freshness decay:** Content from 6 days ago is stale for a weekly newsletter. The ranking model needs a time-decay factor.
- **Signal vs. noise in social media:** Distinguishing genuine technical discussion from hype. Rather than trying to build an automated marketing-vs-technical classifier (too unreliable), we rely on authority scoring, user feedback, and source quality signals to filter noise organically.
- **Graceful failure and escalation:** Production AI systems need to handle edge cases — unparseable newsletters, ambiguous entity matches, API outages — and know when to flag for human review rather than silently failing or producing garbage.

### Differentiators vs. Existing Tools

Existing tools like Feedly, UpContent, and ContentStudio handle parts of this problem. Our unique value comes from combining several things none of them do:

1. **Authority scoring from newsletter cross-referencing.** By ingesting peer newsletters, we build an authority model based on who real editors actually link to — a signal no existing tool provides. This is the strongest differentiator.
2. **Per-user relevance training via feedback loops.** The upvote/downvote system trains a personalized relevance model for each newsletter editor. Over time, the tool learns what *you* consider valuable. Feedly's Leo AI learns preferences, but not in a multi-tenant context where each editor has a separate model.
3. **Unified entity model.** No existing tool links a person's blog, LinkedIn, Bluesky, GitHub, and conference talks into a single profile with an authority score. This gives a holistic view of who matters in the space.
4. **Competitive intelligence.** "These 3 peer newsletters all covered topic X this week, but you haven't." This is a natural output of newsletter ingestion that no curation tool provides.
5. **Historical trend analysis.** "This topic has been growing across sources over the last 4 weeks." Most tools show what's trending *now*; we can show trajectories because we retain content indefinitely.
6. **Topic-tuned relevance.** The vector DB is seeded with domain-specific reference content, so relevance scoring is tuned to the newsletter's niche rather than being generic engagement-based filtering.

## Architecture Overview

### Core Pipeline

The system has three logical stages:

1. **Entity Management** — Build and update databases of people, companies/vendors, and organizations to track. Link their various accounts (LinkedIn, personal site, social media) into unified profiles. Users can upvote/downvote entities to adjust their authority scores.
2. **Content Ingestion** — Pull new content from tracked entities and monitored channels (RSS, social media, newsletters, Reddit). Runs continuously via scheduled background jobs.
3. **Analysis & Surfacing** — Rank, deduplicate, and present the most relevant content for the current newsletter edition. Users upvote/downvote surfaced content to train their personal relevance model.

### User Workflow

The backend is an always-running server with periodic background jobs that scrape and ingest content. The user opens the tool when they have work to do:

- **Weekly (before writing):** Review the dashboard of surfaced content for the current period. Upvote/downvote items. Select content for inclusion in the newsletter.
- **Periodically:** Enrich entity data — link social accounts to profiles, review suggested entity matches, add new entities discovered from newsletter ingestion.
- **Occasionally:** Configure sources, adjust settings, review ingestion health.

No push notifications. The system accumulates and ranks content between user sessions.

### Tech Stack

- **Backend:** Django + Django REST Framework
- **AI Pipeline:** Composable Skills architecture (model-agnostic, Claude-style progressive disclosure format) orchestrated by LangGraph. Multi-model: Claude Sonnet for high-value generation, local models (Ollama) or Claude Haiku for commodity tasks, embeddings for similarity operations.
- **Vector DB:** Self-hosted Qdrant for semantic search over ingested content
- **Relational DB:** PostgreSQL for entities, relationships, ingestion history, authority scores, user feedback, tenant config
- **Background Jobs:** Celery + Redis for scheduled scraping, ingestion runs, and periodic maintenance (content purging)
- **Email Intake:** Resend API for receiving newsletter subscription emails
- **Frontend:** React, designed for non-technical users
- **Design:** Pluggable architecture with clear API contracts for data source plugins

### Multi-Tenant Architecture

Each tenant represents a newsletter. Tenants have:

- Their own set of tracked entities (entities are **not** shared across tenants — the same person may have separate records in different tenants with different authority scores, since someone who is high-authority for a DevOps newsletter may be low-authority for a frontend newsletter)
- Their own relevance model, trained by that editor's upvote/downvote feedback
- Their own newsletter ingestion subscriptions
- Their own content surfacing dashboard, scoped to their topic
- Configurable content retention/purge window (default: 1 year)

> **Implementation note:** Django's built-in auth + a tenant model with ForeignKey relationships on all content/entity tables is sufficient to start. Don't reach for a multi-tenant library like `django-tenants` (which uses Postgres schemas) unless you actually need schema-level isolation. Simple row-level tenant scoping works fine until you have hundreds of tenants.

### Content Retention

Content is stored indefinitely by default, which enables historical trend analysis and authority scoring over time. A configurable per-tenant purge window (e.g. 1 year) runs as a periodic Celery task to clean up old content. The purge should soft-delete or archive rather than hard-delete, so authority score history isn't lost.

## Entity Model

### Three Types of Content Producers

| Type | Content Sources | Social Media Value |
|------|----------------|-------------------|
| **Individuals** | Personal sites, vendor publications, syndication platforms (Substack, DZone, dev.to, Medium) | High — technical discussion, opinions |
| **Vendors** | Company blogs, docs, changelogs, release notes | Low — mostly marketing |
| **Organizations** | Websites of industry groups, standards bodies, NGOs, government agencies | Medium — official announcements |

### Unified Profiles (Entity Resolution)

Each entity should have a unified profile that links together all their accounts: LinkedIn, personal website, GitHub, social media handles, etc.

**This is one of the hardest parts of the project.** Cross-platform identity resolution is a genuinely difficult problem. Consider:

- Name matching is unreliable (John Smith problem, name variations, pseudonyms)
- Not everyone uses consistent handles across platforms
- Automated linking will produce false positives

**Practical approach:** Don't try to fully automate this. Start with manual profile creation (the user adds entities and links their accounts). Over time, add *suggestions* — "this Bluesky account might belong to this person based on bio similarity and shared links" — but require human confirmation. The LLM pipeline could help here by comparing bios and writing samples.

For the MVP, a simple entity form with fields for each platform handle is enough. Automated entity discovery is a later feature.

### Authority Scoring

We need a way to rank content producers, analogous to Ahrefs' Domain Authority but tuned for newsletter relevance.

**The highest quality signal** for adding someone to the system is when they're featured in an existing industry newsletter. That's a human-curated endorsement of relevance.

A composite "Authority Score" could weight several factors:

- **Newsletter mention count:** How often does this person/company appear in newsletters we track? (Strongest signal)
- **Newsletter mention recency:** Recent mentions matter more than old ones
- **Content engagement:** Social shares, Reddit upvotes on their content
- **Publishing frequency:** Active contributors vs. one-off authors
- **Domain expertise signals:** Job title, GitHub contributions, conference talks (harder to automate)

Don't try to build this scoring system perfectly upfront. Start with newsletter-mention-count as the primary signal and add dimensions incrementally. User upvote/downvote feedback on entities provides an additional per-tenant adjustment to authority scores.

## Data Source Plugins

### Plugin Architecture

The pluggable design is a good instinct. Each data source should implement a common interface:

```python
class SourcePlugin:
    def fetch_new_content(since: datetime) -list[ContentItem]
    def get_entity_profile(entity_id) -EntityProfile | None
    def health_check() -bool
```

Each plugin handles its own auth, rate limiting, and API-specific concerns. The core system just calls the interface. A plugin registry and configuration system lets users enable/disable sources and provide API keys.

### Newsletter Ingestion

Subscribing to and parsing existing industry newsletters is the most important data source — they provide both content signals and authority signals. The content from newsletters is "dated" by the time you process it, so it's not directly useful for your own "what's trending" snapshot. Its real value is as an authority signal — who and what are peer newsletters linking to?

Receive newsletters as email via the Resend Inbound API, then use Claude to extract structured link/article data. Use the extracted data for two things: (a) adding mentioned people/companies to the entity database, and (b) tracking what topics peer newsletters are covering.

#### Email Intake via Resend

Use [Resend's Inbound Email](https://resend.com/docs/dashboard/webhooks/introduction) feature:

1. Configure a subdomain (e.g. `inbox.newslettermaker.dev`) with Resend's MX records
2. Resend receives emails to any address at that subdomain and forwards them to our webhook as structured JSON (sender, subject, HTML body, text body, attachments)
3. Each tenant gets a unique intake address (e.g. `tenant-xyz@inbox.newslettermaker.dev`). The user subscribes to peer newsletters using this address.
4. On webhook receipt: store the raw email, queue an LLM extraction job, parse out article links/authors/topics

#### Resend Inbound Limits & Handling

- **Total Volume Limit:** 3,000 emails per month (combined sending and receiving).
- **Total Size Limit:** Inbound emails cannot exceed 40MB after Base64 encoding. Base64 encoding typically increases file size by ~33%, so a 30MB raw email may exceed the limit once encoded.
- **Rejection:** Oversized emails are rejected by the mail server; the sender receives a bounce/NDR message. Resend does **not** strip attachments to fit — the entire message is rejected.
- **Attachments:** Resend's inbound webhooks provide attachment **metadata** and a temporary download URL via the [Attachments API](https://resend.com/docs/api-reference/emails/list-received-email-attachments), rather than including attachment data in the webhook POST payload. Most standard file types are supported; executable files (`.exe`, etc.) are [blocked for security](https://resend.com/docs/dashboard/emails/attachments). Inline images (CID) are treated as attachments and count toward the 40MB limit.
- **Implication for this project:** Newsletter emails are typically text/HTML with embedded images, well under 40MB. The 3,000/month combined limit is the main constraint — at scale, this may require upgrading Resend plans or batching sends. For the MVP with a handful of tenants tracking 10-20 newsletters each, the free tier is sufficient.

#### Newsletter Subscription Confirmation

Most newsletter platforms send a confirmation/double-opt-in email after signup. We need to handle this:

- **Detection:** When a new email arrives from an unrecognized sender, the LLM extraction step should classify it as either "confirmation request" or "newsletter content." Confirmation emails have recognizable patterns (single CTA button, "confirm your subscription" language).
- **Workflow:** Surface unconfirmed subscriptions in the UI with a "pending confirmation" status. Show the user the confirmation link extracted from the email so they can click it manually. Fully automating the click is possible but risks triggering anti-bot measures from newsletter platforms.
- **After confirmation:** Mark the subscription as active. Future emails from that sender go straight to the LLM extraction pipeline.

### RSS Feeds

Track websites/blogs of followed entities and scrape new content as it appears.

Straightforward to implement. Use `feedparser` in Python. Run on a schedule (e.g. every 6 hours). Store seen entry IDs to avoid duplicates. This should be one of the first plugins built — it's simple, reliable, and high value.

### Reddit

A special case — we're watching subreddits for trends, not tracking individual authors.

PRAW makes this easy:
- Monitor specific subreddits (e.g. `r/platformengineering`, `r/devops`, `r/kubernetes`)
- Use `.new()` for recent posts, `.hot()` for trending
- Track upvote velocity as a quality signal
- `.stream()` for real-time monitoring

**Don't try to link Reddit users to entity profiles** — as noted in the original plan, it doesn't matter. Reddit's value is trend detection and community sentiment, not individual tracking. Surface popular questions, recurring pain points, and well-received discussions.

### Social Media Platforms

Watch the output of tracked entities on Bluesky and Mastodon.

**What about tracking for hashtags on Bluesky and Mastodon?**

- **Bluesky:** Open AT Protocol. Full API access. No cost. This is the easiest platform to integrate. **Start here for social media.**

- **Mastodon:** Open ActivityPub protocol. Per-instance APIs, all free. Also easy. **Second priority.**

### LinkedIn with API Details

LinkedIn for enhancing entities, and adding suggestions for articles + their related entities

- **Profile Data:** Can access public profile info (name, headline, location, experience) and connections, but only for authenticated users or approved apps.
- **Keyword Search for Articles:** Not available through official API. Workaround: Google Search with `site:linkedin.com/posts "keyword"` and time filtering.

### Cost Considerations

Agree with the principle of keeping third-party API costs minimal and preferring pay-as-you-go.

**Estimated baseline costs for external services:**

- Bluesky API: Free
- Mastodon API: Free
- Reddit API: Free (within rate limits)
- RSS parsing: Free (self-hosted)
- LLM calls (for content analysis, summarization, classification): Variable — use local models via Ollama (free) for high-volume commodity tasks (classification, relevance scoring), Claude Sonnet for high-value generation tasks (summarization, theme detection, newsletter extraction). See Multi-Model Strategy in the AI Pipeline section. Estimated cost with this split: $20-30/month for Claude API calls.

## AI Pipeline: Composable Skills Architecture

### LangGraph as Orchestrator + Skills as Modules

Based on research documented in [LLM.md](LLM.md), the architecture should use **LangGraph as the orchestrator** and **Claude-style Skills as the domain modules**. This is the "Orchestrator vs. Module" pattern:

- **LangGraph** manages the workflow: deterministic routing, state persistence, conditional edges, human-in-the-loop checkpoints, and recovery from failures at any step.
- **Skills** provide the domain expertise: each is a self-contained module with its own prompt template, input/output schema, error handling, and documentation. LangGraph nodes delegate to Skills for actual LLM work.

This combination is stronger than either approach alone:
- Skills without LangGraph rely on non-deterministic LLM reasoning for orchestration — the model might skip steps or hallucinate new ones.
- LangGraph without Skills forces all prompt logic into graph nodes, creating a monolith that's hard to test or reuse.
- Together, LangGraph provides the deterministic "director" while Skills provide the swappable "actors."

**Key LangGraph benefits for this project:**
- **State persistence:** If the ingestion pipeline fails at deduplication (step 3 of 5), LangGraph can resume from that checkpoint rather than reprocessing from scratch.
- **Conditional routing:** Skip summarization if relevance score is below threshold. Route single-article newsletters to entity extraction instead of link extraction.
- **Human-in-the-loop:** Pause for human review when confidence is low (e.g., ambiguous entity matches).
- **Multi-model routing:** Use cheaper models for high-volume steps and expensive models only where quality matters (see Multi-Model Strategy below).

### Multi-Model Strategy

The Skills architecture should be **model-agnostic**, not locked to Claude. Claude-style Skills (the `.claude/skills/` or `.github/skills/` folder structure with YAML frontmatter, `SKILL.md`, and supporting files) have been adopted as an open standard — GPT models can use them directly in VS Code, and self-hosted models may be able to as well.

Design each Skill with a model-agnostic interface:
- The Skill defines the **prompt template**, **input/output schema**, and **evaluation criteria**
- The **model** is a configuration parameter, not hardcoded
- LangGraph's multi-model routing allows different nodes to use different models

**Recommended model allocation:**

| Skill | Volume | Complexity | Recommended Model |
|-------|--------|------------|-------------------|
| Content Classification | High | Low | Local model (Ollama + Mistral/Llama) or Claude Haiku |
| Relevance Scoring | High | Medium | Embeddings (see below) + local model for explanations |
| Deduplication | High | Low | Embeddings-based (no LLM needed for primary check) |
| Summarization | Medium | High | Claude Sonnet |
| Theme Detection | Low (daily) | High | Claude Sonnet |
| Newsletter Extraction | Low | High | Claude Sonnet |
| Entity Extraction | Low | Medium | Claude Haiku or local model |

This keeps expensive Claude Sonnet calls to the high-value, low-volume tasks where quality matters most. High-volume commodity tasks use embeddings or local models.

### Embeddings: The Cost-Efficient Foundation

**Embeddings** are dense vector representations of text — a way to convert an article, sentence, or paragraph into a list of numbers (typically 768-1536 dimensions) that captures its semantic meaning. Two texts about similar topics will have similar embeddings (measured by cosine similarity), even if they use different words.

Embeddings are:
- **Cheap:** Orders of magnitude cheaper than LLM generation calls. Local embedding models (e.g., `sentence-transformers` or Ollama with `nomic-embed-text`) are free.
- **Fast:** A single embedding call takes milliseconds vs. seconds for an LLM generation.
- **Deterministic:** Same input always produces the same output.

**How embeddings reduce LLM costs in this project:**
- **Relevance scoring:** Instead of asking Claude "is this article relevant to DevOps?" for every item, compute the article's embedding and measure cosine similarity against the newsletter's reference corpus embeddings in Qdrant. Only send borderline cases to an LLM for nuanced judgment.
- **Deduplication:** Compare new content embeddings against recent embeddings. High similarity (>0.92) = likely duplicate. No LLM call needed for the common case.
- **Theme detection:** Cluster recent content embeddings to identify topic groups. The LLM only needs to *label* the clusters, not discover them.

**Embedding model options:**
- **Local (free):** `sentence-transformers/all-MiniLM-L6-v2`, Ollama with `nomic-embed-text`
- **API (cheap):** OpenAI `text-embedding-3-small` (~$0.02/1M tokens), Voyage AI, Cohere Embed

### Claude-Style Skills as Portable Modules

Each Skill follows the progressive disclosure pattern from [LLM.md](LLM.md):

1. **Level 1 (Metadata):** YAML frontmatter with name, description, and trigger keywords. This is all the orchestrator sees during routing.
2. **Level 2 (Instructions):** The `SKILL.md` body with the standard operating procedure — step-by-step instructions, constraints, and references to supporting files.
3. **Level 3 (Resources):** `scripts/`, `references/`, and `assets/` subdirectories containing deterministic code, reference data, and templates.

This structure ensures token efficiency (only load what's needed) and portability (Skills work across Claude, GPT, and potentially local models).

### Skill Catalog

Each skill is a standalone module with a defined interface. The model used is configurable per-skill (not hardcoded to Claude):

1. **Content Classification:** Given raw content, classify as: technical article, tutorial, opinion piece, product announcement, event, release notes, other. Returns structured classification with confidence.
2. **Relevance Scoring:** Given content + a newsletter's topic description + reference corpus from the vector DB, score relevance 0-1 with explanation. Uses semantic similarity against reference embeddings as a signal alongside Claude's judgment.
3. **Deduplication / Clustering:** Given a new content item + recent embeddings from Qdrant, determine if this covers a topic already ingested. If so, pick the best version (highest authority source, most comprehensive coverage).
4. **Summarization:** Given an article, generate a newsletter-ready summary (2-3 sentences) that a non-technical editor could use directly or edit.
5. **Theme Detection:** Given all content ingested in the current period, identify 3-5 emerging themes and suggest them as newsletter section topics.
6. **Newsletter Email Extraction:** Given raw newsletter HTML, extract structured data: list of article links, titles, authors, brief descriptions, and the newsletter's name/date.
7. **Entity Extraction:** Given an article or newsletter, identify mentioned people, companies, and organizations. Suggest matches against existing entity profiles.

### Default Pipeline Orchestration

The standard content ingestion flow chains skills in order:

```
New Content → Classification → Relevance Scoring → (if relevant) → Deduplication → Summarization
                                                    (if not relevant) → archive, skip remaining steps
```

Theme Detection runs separately on a schedule (e.g., when the user opens the dashboard, or daily).

Newsletter Email Extraction and Entity Extraction run when new newsletter emails arrive via Resend. The Newsletter Email Extraction skill should distinguish between curated/roundup newsletters (extract links and authors) and single-article newsletters (treat the author as the primary signal for entity authority scoring). This classification should happen at ingestion time, since even newsletters that are typically one format may have special editions in the other format.

> **On LangGraph:** The orchestrator is implemented as a LangGraph StateGraph. This gives conditional routing (skip summarization if relevance is low, route single-article newsletters differently), state persistence (resume from failures), human-in-the-loop checkpoints, and multi-model routing. Each graph node delegates to a standalone Skill module, keeping the Skills framework-agnostic and independently testable. The LangGraph layer is an implementation detail of the orchestrator — the Skills themselves have no dependency on it.

### Vector DB Role

Qdrant stores embeddings of all ingested content. Used by multiple skills:

- **Deduplication skill:** similarity search to find near-duplicate content
- **Relevance scoring skill:** compare against reference corpus embeddings for the newsletter's topic
- **Theme detection skill:** cluster recent embeddings to identify emerging topic groups
- **Entity extraction skill:** compare bio text / writing samples for entity matching suggestions

## Scope and Phasing

**The single biggest risk with this project is scope.** As described, it encompasses: 6+ platform integrations, entity resolution, authority scoring, an LLM analysis pipeline, a vector database, a relational database, a React UI, a plugin system, and newsletter generation assistance. That's easily 3-6 months of focused work for one person.

A phased approach is essential:

### Phase 1: MVP — Content Ingestion + Basic Surfacing

**Goal:** Ingest content from easy sources, store it, and surface the most relevant items for a newsletter edition.

- RSS feed plugin (track 20-30 blogs/sites manually configured)
- Reddit plugin (monitor 3-5 subreddits)
- Basic entity model in Postgres (manually created profiles)
- Vector DB (Qdrant) for content embeddings
- Composable skills: classification, relevance scoring, summarization (each standalone, chained by default orchestrator)
- Minimal UI: dashboard showing top content for the current period, sorted by relevance. Upvote/downvote buttons.
- Seed script that pre-populates with sample data for demo purposes (e.g., a month of RSS content from platform engineering blogs, a dozen parsed newsletters, pre-created entity profiles with linked accounts). This makes the project immediately demo-able without weeks of data accumulation.
- No authority scoring, no social media, no newsletter ingestion yet

### Phase 2: Newsletter Ingestion + Authority Signals

- Newsletter email ingestion via Resend with Claude-based extraction
- Subscription confirmation flow in UI
- Authority scoring based on newsletter mention frequency
- Bluesky plugin (easiest social media API)
- Deduplication skill added to pipeline
- Entity extraction skill: auto-suggest new entities from ingested newsletters
- Entity profile linking (still mostly manual, with LLM-suggested matches)

### Phase 3: Expanded Sources + Intelligence

- Mastodon plugin
- Trend velocity detection
- Theme suggestion for upcoming newsletter
- Source diversity analysis
- Original content idea generation ("Our Insight" suggestions)

### Phase 4: Polish + Advanced Features

- LinkedIn integration (if feasible)
- Automated entity discovery from ingested content
- Full authority scoring model with multiple signals
- Newsletter draft generation / templating (connect to GENRES.md layout types)

## Feedback Loop Design

When a user upvotes / downvotes surfaced content, the feedback needs to flow back into the system to improve future relevance. Four options were considered:

### Option A: Adjust Authority Scores of the Source Entity

The upvote/downvote modifies the authority score of the entity (person/company) that produced the content.

| | |
|---|---|
| **Benefits** | Simple to implement. A single numeric adjustment per entity per tenant. Naturally surfaces more content from authors the editor trusts. Compounds over time — consistently good sources float up. |
| **Drawbacks** | Coarse-grained: penalizes/rewards the *source* when the issue might be the *topic*. An author you generally like might write one irrelevant article — downvoting shouldn't tank their authority. Doesn't capture topical preferences at all. |

### Option B: Store Feedback as Labeled Training Data

Store each upvote/downvote as a labeled example (content features → relevant/not-relevant). Periodically use these examples to refine the relevance scoring prompt via few-shot examples or fine-tuning.

| | |
|---|---|
| **Benefits** | Captures nuanced preferences that authority scores miss (topic, format, depth). Gets smarter over time with more data. The labeled dataset is reusable for evaluation and regression testing. |
| **Drawbacks** | Requires a meaningful volume of feedback before it improves anything (~50-100+ labeled examples). Prompt engineering with few-shot examples has context window limits. Fine-tuning is expensive and operationally complex for a multi-tenant system. Latency between feedback and improvement (batch retraining). |

### Option C: Adjust Vector Similarity Weights

Use feedback to shift the tenant's "topic centroid" in embedding space. Upvoted content's embeddings pull the centroid toward similar content; downvoted content pushes it away.

| | |
|---|---|
| **Benefits** | Mathematically elegant. Works at the semantic level — captures what topics and styles the editor prefers, not just which sources. Fast to compute. No LLM calls needed for the feedback loop itself. |
| **Drawbacks** | Hardest to implement correctly. Requires careful tuning of learning rate (how much does one vote shift the centroid?). Can drift in unintuitive ways with sparse feedback. Difficult to explain to users ("why did this get ranked higher?"). Debugging is opaque. |

### Implementation: Combination

Use a weighted combination, phased over time:

- **Phase 1 (MVP):** Option A only — adjust entity authority scores. Simple, immediate, and covers the most common case ("I trust this author" / "this source is noise").
- **Phase 2:** Add Option C — build a per-tenant topic centroid from upvoted content embeddings. Use cosine similarity to the centroid as an additional relevance signal alongside authority score.
- **Phase 3:** Add Option B — accumulate labeled examples and use them as few-shot examples in the relevance scoring prompt. This adds the nuanced "what does this specific editor value?" signal.

The final relevance score becomes: `weighted_sum(embedding_similarity, authority_score, feedback_adjusted_score)` with weights tunable per tenant.

## Composable UI Design

Here are possibilities for non-technical users chaining primitives into workflows from simplest to most ambitious:

### Level 1: Contextual Skill Actions (MVP)

Individual skills are exposed as actions on content items throughout the UI. When viewing any article, the user sees action buttons or a right-click menu:

- **"Summarize"** — runs the Summarization skill on this article, shows the result inline
- **"Find related"** — runs the Deduplication / similarity skill to surface related content
- **"Extract entities"** — runs Entity Extraction and shows suggested people / companies to add
- **"Check relevance"** — runs Relevance Scoring and explains why this item was ranked where it is

This is the simplest approach and covers most real use cases. It demonstrates that skills are independently invocable, not locked inside the pipeline.

### Level 2: Multi-Step Skill Chaining

A "Run Skills" panel where the user selects a content item, then picks an ordered sequence of skills to run. The output of each step feeds into the next. Example workflow a user might build:

1. Select an article → **Summarize** → **Entity Extraction** → auto-create entity profiles from the summary
2. Select a newsletter email → **Newsletter Extraction** → **Relevance Scoring** on each extracted link → show only relevant links

The UI would show a simple linear pipeline builder (drag skills into a sequence) with a preview of each step's output.

### Level 3: Saved Workflows / Templates

Let users save their custom skill chains as named workflows they can re-run. Example: "My weekly prep" = run Theme Detection → show top 20 items → auto-summarize the top 5. These saved workflows would also serve as great demo material.

**Recommendation:** Start with Level 1 for the MVP — it's low implementation cost and directly demonstrates composability. Level 2 is a strong Phase 3/4 feature. Level 3 is a nice-to-have stretch goal.

## Monitoring and Observability

### Recommended Approach: Django-Native with a Lightweight External Stack

For a portfolio project at this scale, a hybrid approach balances production-readiness with operational simplicity:

**Built into Django + the React UI:**
- **Ingestion health dashboard:** A dedicated UI page showing the status of each data source plugin — last successful fetch, error count, current status (healthy/degraded/failing). Backed by a Django model that logs each ingestion run.
- **Human review queue:** A UI page listing items flagged by skills as low-confidence (e.g., ambiguous entity matches, classification confidence < 0.6, articles that might be duplicates but aren't certain). Users can resolve these manually.
- **Skill execution logs:** A Django model logging each skill invocation — input, output, model used, latency, success/failure, confidence score. Viewable in the UI as a filterable activity log.

**External lightweight stack (optional, Phase 3+):**
- **Structured logging:** Use Python's `structlog` to emit JSON logs from the Django app and Celery workers. These can be consumed by any log aggregator.
- **Prometheus metrics:** Expose key metrics via `django-prometheus` — skill execution latency, ingestion success/failure rates, queue depth, API response times. Minimal setup if deploying to Kubernetes.
- **Grafana dashboards:** Connect to Prometheus for operational dashboards. Useful but not essential for MVP.

**Skip for this project:** Full ELK/Loki stack, distributed tracing (OpenTelemetry), APM tools. These are overkill for a single-server portfolio project.

The Django-native monitoring is the priority — it's part of the product UX and demonstrates the "production agents that know when to escalate" principle. External observability is infrastructure polish for later.

## Deployment - Docker Compose for MVP, Kubernetes-Ready

**Phase 1 — Docker Compose on a single VM:**

A `docker-compose.yml` that runs all services:
- Django app (gunicorn)
- Celery worker + Celery beat (scheduled tasks)
- PostgreSQL
- Redis (Celery broker + cache)
- Qdrant (vector DB)
- Nginx (reverse proxy + static files)

Deploy to a single VPS (e.g., Hetzner, DigitalOcean, Railway). Total cost: ~$20-40/month.

**Phase 2+ — Kubernetes-ready:**

The Docker Compose setup naturally translates to Kubernetes manifests or a Helm chart:
- Each service becomes a Deployment + Service
- PostgreSQL and Redis can move to managed services (RDS, ElastiCache) or remain in-cluster
- Qdrant can move to Qdrant Cloud or remain self-hosted
- Celery workers scale independently via HPA
- Ingress replaces Nginx

**What to build now (even for Docker Compose):**
- Dockerfiles for the Django app and Celery worker
- Environment-based configuration (12-factor app style) — database URLs, API keys, model endpoints all via environment variables
- Health check endpoints (`/healthz`, `/readyz`) for each service
- A `just` file with common commands (`make dev`, `make seed`, `make test`)

**Skip for now:** Terraform/IaC for infrastructure provisioning, CI/CD pipelines (GitHub Actions is fine for builds), multi-region deployment.

## Open Questions

1. **Multi-model compatibility testing.** ~~The Skills architecture is designed to be model-agnostic, and GPT models are confirmed to work with Claude-style Skills in VS Code. We should evaluate which local/self-hosted models (via Ollama) can effectively consume the progressive disclosure Skill format. This affects our cost model — if local models handle Skills well, the high-volume commodity tasks (classification, relevance scoring) can run at zero marginal cost. **Action:** Set up a test harness that runs each Skill against multiple models and compares output quality.~~

   **Resolved.** Research on self-hosted model compatibility is documented in the "Claude Skills with Self-Hosted LLMs" section of [LLM.md](LLM.md). Key findings: the progressive disclosure model is a system design pattern, not a model feature — it requires a "Skill Loader" runtime layer in LangGraph. Best local model candidates are **Qwen 2.5 72B** (strongest tool discovery), **Command R+** (best SOP adherence), and **Llama 3.1 70B** (reliable generalist). The LangGraph implementation handles all three tiers: a registry init node for Level 1 metadata, a `load_skill()` tool call for Level 2, and a `run_script()` tool call for Level 3. Remaining action: build the test harness to benchmark each Skill against these models and compare output quality — this is an implementation task, not an open design question.

2. **Feedback loop implementation details.** The phased approach (entity authority → topic centroid → few-shot examples) is the plan, but concrete implementation questions remain:
   - What's the right learning rate for authority score adjustments? (e.g., +0.1 per upvote, -0.05 per downvote, with decay?)
   - How many feedback signals before the topic centroid becomes useful?
   - Should downvotes have stronger weight than upvotes (negativity bias)?

   **Decision: Expose as admin-configurable controls.** Rather than hardcoding these values, the admin UI should expose them as adjustable settings per tenant. This lets each newsletter editor (or the system administrator) tune the feedback loop to their domain without code changes.

   **Admin controls to expose:**

   | Control | Default | Range | Notes |
   |---------|---------|-------|-------|
   | Upvote authority weight | +0.1 | 0.01–0.5 | How much a single upvote boosts an entity's authority score |
   | Downvote authority weight | -0.05 | -0.5–0 | How much a single downvote penalizes. Default asymmetric (weaker than upvote) to avoid a single bad article tanking a good source |
   | Authority score decay rate | 0.95/month | 0.8–1.0 | Multiplicative monthly decay so stale entities don't dominate. 1.0 = no decay |
   | Centroid learning rate | 0.05 | 0.01–0.2 | How aggressively the topic centroid shifts per feedback signal |
   | Centroid activation threshold | 30 signals | 10–100 | Minimum feedback count before the centroid influences relevance scoring |
   | Negativity bias multiplier | 1.5x | 1.0–3.0 | Whether downvotes shift the centroid more than upvotes (1.0 = symmetric) |

   **Implementation approach:** Store these as a JSON config field on the Tenant model with sensible defaults. The admin UI renders them as sliders/number inputs with min/max bounds. Include a "Reset to defaults" button. Add a "Preview impact" feature in Phase 3 that shows how changing a value would re-rank the current dashboard.

   **Why asymmetric defaults (upvote > downvote)?** A new system has sparse data. If downvotes are too aggressive, a single misfire (e.g., a great author writes one off-topic piece) permanently buries them. It's safer to let good signals accumulate gradually and let bad signals have a gentler effect. Users who want stronger negativity bias can increase the multiplier.

3. **Composable UI scope for MVP.** Level 1 (contextual skill actions) is planned for MVP.

   ### Skill Actions: UI Implementation Sketch

   At its core, this is a request-response pattern with a status lifecycle. Each skill action follows the same flow: user triggers → loading state → result displayed → user acts on result.

   **Content Detail View (the primary interaction surface):**

   When a user views a content item (article, post, etc.) from the dashboard, the detail panel includes a "Skills" toolbar:

   ```
   ┌─────────────────────────────────────────────────────┐
   │ Article: "Kubernetes 1.31 Release Highlights"       │
   │ Source: kubernetes.io/blog  •  2 days ago            │
   │ Relevance: 0.87  •  Authority: 0.72                 │
   ├─────────────────────────────────────────────────────┤
   │ [📝 Summarize] [🔍 Find Related] [👤 Extract Entities] [📊 Explain Relevance] │
   ├─────────────────────────────────────────────────────┤
   │ ▼ Summary (generated 2 min ago)                     │
   │ ┌─────────────────────────────────────────────────┐ │
   │ │ Kubernetes 1.31 introduces native sidecar       │ │
   │ │ container support and graduates several...      │ │
   │ │                            [Copy] [Regenerate]  │ │
   │ └─────────────────────────────────────────────────┘ │
   │                                                     │
   │ ▼ Extracted Entities (generated 5 min ago)          │
   │ ┌─────────────────────────────────────────────────┐ │
   │ │ • Tim Hockin (Google) — matched existing entity │ │
   │ │ • SIG Node — new, [Add to Entities]             │ │
   │ └─────────────────────────────────────────────────┘ │
   └─────────────────────────────────────────────────────┘
   ```

   **Backend implementation:**

   - **API endpoint:** `POST /api/v1/content/{id}/skills/{skill_name}/` — triggers the skill, returns a `SkillResult` object with status (pending/running/completed/failed), result data, and metadata (model used, latency, confidence).
   - **Async execution:** Skills that take >1s (summarization, entity extraction) should run via Celery and return a `202 Accepted` with a result ID. The frontend polls or uses WebSocket for completion. Classification and relevance explanations are fast enough for synchronous response.
   - **Error handling:** If a skill fails (model timeout, malformed input), the API returns the error in the `SkillResult` with status `failed` and a user-readable message. The UI shows an inline error with a "Retry" button. No silent failures.
   - **Django models:**

   ```python
   class SkillResult(models.Model):
       content = models.ForeignKey(Content, on_delete=models.CASCADE, related_name='skill_results')
       tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
       skill_name = models.CharField(max_length=64)  # e.g. "summarization", "entity_extraction"
       status = models.CharField(choices=STATUS_CHOICES)  # pending, running, completed, failed
       result_data = models.JSONField(null=True)  # skill-specific structured output
       error_message = models.TextField(blank=True)
       model_used = models.CharField(max_length=64)  # e.g. "claude-sonnet-4", "ollama/mistral"
       latency_ms = models.IntegerField(null=True)
       confidence = models.FloatField(null=True)
       created_at = models.DateTimeField(auto_now_add=True)

       class Meta:
           indexes = [
               models.Index(fields=['content', 'skill_name']),
               models.Index(fields=['tenant', 'created_at']),
           ]
   ```

   **Frontend implementation:**

   - React component: `<SkillActionBar>` renders the skill buttons for a content item. Each button triggers the API call and manages its own loading/result/error state.
   - Results render inline below the toolbar in collapsible sections. Multiple skill results can be open simultaneously.
   - Loading state: button shows a spinner, disabled to prevent duplicate submissions.
   - Each result section has action buttons relevant to that skill (Copy, Regenerate, Add to Entities, etc.).

   ### Persistence: Should Skill Results Be Saved?

   **Recommendation: Yes, persist by default.** The cost is low and the benefits are significant.

   **What we gain by persisting:**

   - **No redundant LLM calls.** If a user summarizes an article on Monday and returns Wednesday, the summary is already there. Without persistence, they'd re-trigger the skill and pay for another LLM call. At $0.003-0.01 per summarization, this adds up across hundreds of articles.
   - **Audit trail.** The skill execution log (model used, latency, confidence) is valuable for debugging relevance issues and tuning the pipeline. "Why was this article ranked so high?" becomes answerable by inspecting the persisted relevance explanation.
   - **Cross-user visibility (future).** If multiple editors share a tenant, one editor's entity extraction results are visible to others without re-running.
   - **Evaluation dataset.** Persisted results + user feedback (did they use the summary? edit it? discard it?) become training data for improving skill prompts over time.
   - **Offline/async use.** Background jobs can pre-run skills (e.g., auto-summarize all items above relevance 0.8) and have results ready when the user opens the dashboard.

   **What we lose by persisting:**

   - **Staleness risk.** A summary generated with an older model version or before the article was updated might be misleading. Mitigation: show the generation timestamp, and offer a "Regenerate" button that creates a new result (keeping the old one for comparison).
   - **Storage cost.** See estimates below — this is negligible.
   - **Complexity.** Need to handle versioning (multiple results for the same content+skill pair) and cleanup. But the `SkillResult` model above already handles this naturally.

   **Storage estimates:**

   | Skill | Avg result size | Volume (1 tenant, 1 year) | Storage |
   |-------|----------------|---------------------------|---------|
   | Summarization | ~500 bytes (2-3 sentences) | 2,000 articles × 1 result | ~1 MB |
   | Entity Extraction | ~1 KB (list of entities + metadata) | 2,000 articles × 1 result | ~2 MB |
   | Relevance Explanation | ~300 bytes | 5,000 articles × 1 result | ~1.5 MB |
   | Classification | ~100 bytes | 5,000 articles × 1 result | ~0.5 MB |
   | Find Related | ~2 KB (list of related item IDs + scores) | 500 manual invocations | ~1 MB |
   | **Total per tenant/year** | | | **~6 MB** |

   At ~6 MB per tenant per year in the `result_data` JSON field, storage is a non-issue even at hundreds of tenants. PostgreSQL handles this comfortably. The content embeddings in Qdrant (768-1536 floats per article) dwarf this by orders of magnitude.

   **Versioning policy:** Keep the latest result per content+skill pair as the "active" result. If the user clicks "Regenerate," create a new `SkillResult` row and mark the previous one as superseded (a `superseded_by` FK or a boolean). Purge superseded results older than 90 days via the same Celery cleanup task that handles content retention.

## Reference Links

- See [NOTES.md](NOTES.md) for research on existing content discovery / curation tools
- See [GENRES.md](GENRES.md) for newsletter format types and layout templates
- See [IMPLEMENTATION.md](IMPLEMENTATION.md) for additional implementation notes
- See [LLM.md](LLM.md) for research on Claude Skills architecture, LangGraph integration, and multi-model considerations

