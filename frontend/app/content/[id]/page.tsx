import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { StatusBadge } from "@/components/status-badge";
import { getTenantContent, getTenantFeedback, getTenantReviewQueue, getTenantSkillResults, getTenants } from "@/lib/api";
import { formatDate, formatScore, getErrorMessage, getSuccessMessage, selectTenant } from "@/lib/view-helpers";

type ContentDetailPageProps = {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function ContentDetailPage({ params, searchParams }: ContentDetailPageProps) {
  const [{ id }, resolvedSearchParams] = await Promise.all([params, searchParams]);
  const tenants = await getTenants();
  const selectedTenant = selectTenant(tenants, resolvedSearchParams);

  if (!selectedTenant) {
    return (
      <AppShell
        title="Content detail"
        description="No tenant is available for the configured API user."
        tenants={[]}
        selectedTenantId={null}
      >
        <div className="empty-state">Create a tenant first in Django admin.</div>
      </AppShell>
    );
  }

  const contentId = Number.parseInt(id, 10);
  const [content, skillResults, reviewQueue, feedback] = await Promise.all([
    getTenantContent(selectedTenant.id, contentId),
    getTenantSkillResults(selectedTenant.id),
    getTenantReviewQueue(selectedTenant.id),
    getTenantFeedback(selectedTenant.id),
  ]);
  const errorMessage = getErrorMessage(resolvedSearchParams);
  const successMessage = getSuccessMessage(resolvedSearchParams);
  const contentSkillResults = skillResults.filter((item) => item.content === content.id);
  const reviewItems = reviewQueue.filter((item) => item.content === content.id);
  const contentFeedback = feedback.filter((item) => item.content === content.id);
  const upvotes = contentFeedback.filter((item) => item.feedback_type === "upvote").length;
  const downvotes = contentFeedback.filter((item) => item.feedback_type === "downvote").length;
  const canSummarize = (content.relevance_score ?? 0) >= 0.7;

  return (
    <AppShell
      title="Content detail"
      description="Inspect the raw article, persisted skill outputs, and editorial status for a single content item."
      tenants={tenants}
      selectedTenantId={selectedTenant.id}
    >
      {errorMessage ? <div className="error-banner">{errorMessage}</div> : null}
      {successMessage ? <div className="empty-state">{successMessage}</div> : null}
      <section className="detail-grid">
        <div className="stack">
          <article className="detail-hero">
            <div className="detail-hero__header">
              <div className="stack">
                <p className="eyebrow">{content.source_plugin}</p>
                <h3>{content.title}</h3>
                <div className="meta-row">
                  <span>{formatDate(content.published_date)}</span>
                  <span>{content.author || "Unknown author"}</span>
                  <span>{content.content_type || "unclassified"}</span>
                </div>
              </div>
              <StatusBadge tone={(content.relevance_score ?? 0) >= 0.7 ? "positive" : "warning"}>
                Relevance {formatScore(content.relevance_score)}
              </StatusBadge>
            </div>

            <div className="action-row">
              <Link className="button-link" href={content.url} target="_blank">
                Open source
              </Link>
              <form action="/api/feedback" method="POST">
                <input type="hidden" name="tenantId" value={selectedTenant.id} />
                <input type="hidden" name="contentId" value={content.id} />
                <input type="hidden" name="feedbackType" value="upvote" />
                <input type="hidden" name="redirectTo" value={`/content/${content.id}?tenant=${selectedTenant.id}`} />
                <button className="button" type="submit">
                  Upvote
                </button>
              </form>
              <form action="/api/feedback" method="POST">
                <input type="hidden" name="tenantId" value={selectedTenant.id} />
                <input type="hidden" name="contentId" value={content.id} />
                <input type="hidden" name="feedbackType" value="downvote" />
                <input type="hidden" name="redirectTo" value={`/content/${content.id}?tenant=${selectedTenant.id}`} />
                <button className="ghost-button" type="submit">
                  Downvote
                </button>
              </form>
            </div>

            <div className="detail-body">{content.content_text}</div>
          </article>

          <article className="skill-card stack">
            <p className="eyebrow">Skill action bar</p>
            <div className="action-row">
              <form action="/api/skills/summarization" method="POST">
                <input type="hidden" name="tenantId" value={selectedTenant.id} />
                <input type="hidden" name="contentId" value={content.id} />
                <input type="hidden" name="redirectTo" value={`/content/${content.id}?tenant=${selectedTenant.id}`} />
                <button className="ghost-button" type="submit" disabled={!canSummarize}>
                  Summarize
                </button>
              </form>
              <form action="/api/skills/relevance_scoring" method="POST">
                <input type="hidden" name="tenantId" value={selectedTenant.id} />
                <input type="hidden" name="contentId" value={content.id} />
                <input type="hidden" name="redirectTo" value={`/content/${content.id}?tenant=${selectedTenant.id}`} />
                <button className="ghost-button" type="submit">
                  Explain relevance
                </button>
              </form>
              <form action="/api/skills/find_related" method="POST">
                <input type="hidden" name="tenantId" value={selectedTenant.id} />
                <input type="hidden" name="contentId" value={content.id} />
                <input type="hidden" name="redirectTo" value={`/content/${content.id}?tenant=${selectedTenant.id}`} />
                <button className="ghost-button" type="submit">
                  Find related
                </button>
              </form>
            </div>
            <p className="meta-copy">
              These controls create new persisted SkillResult records. Summarization is only available once a content item has
              reached a relevance score of at least 0.70.
            </p>
          </article>

          {contentSkillResults.map((skillResult) => (
            <article key={skillResult.id} className="skill-card stack">
              <div className="content-card__header">
                <div>
                  <p className="eyebrow">{skillResult.skill_name}</p>
                  <h3>{skillResult.status}</h3>
                </div>
                <StatusBadge
                  tone={
                    skillResult.status === "completed"
                      ? "positive"
                      : skillResult.status === "failed"
                        ? "negative"
                        : "warning"
                  }
                >
                  {skillResult.model_used || "model pending"}
                </StatusBadge>
              </div>
              <div className="meta-row">
                <span>Created {formatDate(skillResult.created_at)}</span>
                <span>Latency {skillResult.latency_ms ?? 0} ms</span>
                <span>Confidence {formatScore(skillResult.confidence)}</span>
              </div>
              {skillResult.error_message ? <div className="error-banner">{skillResult.error_message}</div> : null}
              <pre>{JSON.stringify(skillResult.result_data, null, 2)}</pre>
            </article>
          ))}
        </div>

        <aside className="stack">
          <article className="card">
            <p className="eyebrow">Feedback</p>
            <p className="card-value">{upvotes}/{downvotes}</p>
            <p className="card-note">Upvotes and downvotes recorded for this item.</p>
          </article>

          <article className="card stack">
            <p className="eyebrow">Review state</p>
            {reviewItems.length === 0 ? <p className="meta-copy">No review flags are attached to this content.</p> : null}
            {reviewItems.map((item) => (
              <div key={item.id} className="stack">
                <StatusBadge tone={item.resolved ? "neutral" : "warning"}>{item.reason}</StatusBadge>
                <p className="meta-copy">Confidence {formatScore(item.confidence)}</p>
                <p className="meta-copy">{item.resolved ? item.resolution || "resolved" : "Awaiting human resolution"}</p>
              </div>
            ))}
          </article>

          <article className="card stack">
            <p className="eyebrow">Navigate</p>
            <Link className="button-link" href={`/?tenant=${selectedTenant.id}`}>
              Back to dashboard
            </Link>
            <Link className="ghost-button" href={`/entities?tenant=${selectedTenant.id}`}>
              Manage entities
            </Link>
          </article>
        </aside>
      </section>
    </AppShell>
  );
}