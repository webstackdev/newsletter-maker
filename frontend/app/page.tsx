import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { StatusBadge } from "@/components/status-badge";
import {
  getTenantContents,
  getTenantEntities,
  getTenantFeedback,
  getTenantReviewQueue,
  getTenantSourceConfigs,
  getTenants,
} from "@/lib/api";
import { formatDate, formatScore, getErrorMessage, getSearchParam, getSuccessMessage, selectTenant, truncateText } from "@/lib/view-helpers";

type HomePageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function HomePage({ searchParams }: HomePageProps) {
  const resolvedSearchParams = await searchParams;
  const tenants = await getTenants();
  const selectedTenant = selectTenant(tenants, resolvedSearchParams);

  if (!selectedTenant) {
    return (
      <AppShell
        title="Dashboard"
        description="Create a tenant in Django admin first, then come back here to review ingested content."
        tenants={[]}
        selectedTenantId={null}
      >
        <div className="empty-state">No tenants are available for the configured API user.</div>
      </AppShell>
    );
  }

  const view = getSearchParam(resolvedSearchParams, "view") || "content";
  const contentTypeFilter = getSearchParam(resolvedSearchParams, "contentType");
  const sourceFilter = getSearchParam(resolvedSearchParams, "source");
  const daysFilter = Number.parseInt(getSearchParam(resolvedSearchParams, "days") || "30", 10);

  const [contents, reviewQueue, entities, sourceConfigs, feedback] = await Promise.all([
    getTenantContents(selectedTenant.id),
    getTenantReviewQueue(selectedTenant.id),
    getTenantEntities(selectedTenant.id),
    getTenantSourceConfigs(selectedTenant.id),
    getTenantFeedback(selectedTenant.id),
  ]);

  const activeContents = contents.filter((content) => content.is_active);
  const thresholdDate = new Date();
  thresholdDate.setDate(thresholdDate.getDate() - (Number.isNaN(daysFilter) ? 30 : daysFilter));

  const filteredContents = activeContents
    .filter((content) => !contentTypeFilter || content.content_type === contentTypeFilter)
    .filter((content) => !sourceFilter || content.source_plugin === sourceFilter)
    .filter((content) => new Date(content.published_date) >= thresholdDate)
    .sort((left, right) => {
      const relevanceDelta = (right.relevance_score ?? -1) - (left.relevance_score ?? -1);
      if (relevanceDelta !== 0) {
        return relevanceDelta;
      }
      return new Date(right.published_date).getTime() - new Date(left.published_date).getTime();
    });

  const contentMap = new Map(contents.map((content) => [content.id, content]));
  const pendingReviewItems = reviewQueue.filter((item) => !item.resolved);
  const contentTypes = Array.from(new Set(activeContents.map((content) => content.content_type).filter(Boolean))).sort();
  const sources = Array.from(new Set(activeContents.map((content) => content.source_plugin))).sort();
  const positiveFeedback = feedback.filter((item) => item.feedback_type === "upvote").length;
  const negativeFeedback = feedback.filter((item) => item.feedback_type === "downvote").length;
  const errorMessage = getErrorMessage(resolvedSearchParams);
  const successMessage = getSuccessMessage(resolvedSearchParams);

  return (
    <AppShell
      title={`${selectedTenant.name} dashboard`}
      description="Ranked content, pending human review, and quick editorial actions backed by the current Django API."
      tenants={tenants}
      selectedTenantId={selectedTenant.id}
    >
      <section className="stats-grid">
        <article className="card">
          <p className="eyebrow">Surfaced</p>
          <p className="card-value">{filteredContents.length}</p>
          <p className="card-note">Active content items in the current filter window.</p>
        </article>
        <article className="card">
          <p className="eyebrow">Review queue</p>
          <p className="card-value">{pendingReviewItems.length}</p>
          <p className="card-note">Borderline or low-confidence items waiting on an editor.</p>
        </article>
        <article className="card">
          <p className="eyebrow">Tracked entities</p>
          <p className="card-value">{entities.length}</p>
          <p className="card-note">People, vendors, and organizations linked to this tenant.</p>
        </article>
        <article className="card">
          <p className="eyebrow">Signals</p>
          <p className="card-value">{positiveFeedback}/{negativeFeedback}</p>
          <p className="card-note">Upvotes and downvotes captured through the API so far.</p>
        </article>
      </section>

      {errorMessage ? <div className="error-banner">{errorMessage}</div> : null}
      {successMessage ? <div className="empty-state">{successMessage}</div> : null}

      <form className="filter-bar" method="GET">
        <input type="hidden" name="tenant" value={selectedTenant.id} />
        <div className="field">
          <label htmlFor="view">View</label>
          <select id="view" name="view" defaultValue={view}>
            <option value="content">Surfaced content</option>
            <option value="review">Pending review</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="contentType">Content type</label>
          <select id="contentType" name="contentType" defaultValue={contentTypeFilter}>
            <option value="">All types</option>
            {contentTypes.map((contentType) => (
              <option key={contentType} value={contentType}>
                {contentType}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="source">Source</label>
          <select id="source" name="source" defaultValue={sourceFilter}>
            <option value="">All sources</option>
            {sources.map((source) => (
              <option key={source} value={source}>
                {source}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="days">Published within</label>
          <select id="days" name="days" defaultValue={String(daysFilter)}>
            <option value="7">7 days</option>
            <option value="14">14 days</option>
            <option value="30">30 days</option>
            <option value="90">90 days</option>
          </select>
        </div>
        <div className="filter-actions">
          <button className="button" type="submit">
            Apply filters
          </button>
          <Link className="ghost-button" href={`/?tenant=${selectedTenant.id}`}>
            Reset
          </Link>
        </div>
      </form>

      {view === "review" ? (
        <section className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Content</th>
                <th>Reason</th>
                <th>Confidence</th>
                <th>Queued</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {pendingReviewItems.length === 0 ? (
                <tr>
                  <td colSpan={5}>
                    <div className="empty-state">No unresolved review items for this tenant right now.</div>
                  </td>
                </tr>
              ) : null}
              {pendingReviewItems.map((item) => {
                const content = contentMap.get(item.content);
                return (
                  <tr key={item.id}>
                    <td>
                      <strong>{content?.title ?? `Content #${item.content}`}</strong>
                      <div className="meta-row">
                        <span>{content?.source_plugin ?? "unknown source"}</span>
                        <span>{content?.content_type || "unclassified"}</span>
                      </div>
                    </td>
                    <td>{item.reason}</td>
                    <td>{formatScore(item.confidence)}</td>
                    <td>{formatDate(item.created_at)}</td>
                    <td>
                      <div className="action-row">
                        <form action={`/api/review/${item.id}`} method="POST">
                          <input type="hidden" name="tenantId" value={selectedTenant.id} />
                          <input type="hidden" name="resolved" value="true" />
                          <input type="hidden" name="resolution" value="human_approved" />
                          <input type="hidden" name="redirectTo" value={`/?tenant=${selectedTenant.id}&view=review`} />
                          <button className="button" type="submit">
                            Approve
                          </button>
                        </form>
                        <form action={`/api/review/${item.id}`} method="POST">
                          <input type="hidden" name="tenantId" value={selectedTenant.id} />
                          <input type="hidden" name="resolved" value="true" />
                          <input type="hidden" name="resolution" value="human_rejected" />
                          <input type="hidden" name="redirectTo" value={`/?tenant=${selectedTenant.id}&view=review`} />
                          <button className="ghost-button" type="submit">
                            Reject
                          </button>
                        </form>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      ) : (
        <section className="content-grid">
          <div className="stack">
            {filteredContents.length === 0 ? <div className="empty-state">No content matched the current filters.</div> : null}
            {filteredContents.map((content) => (
              <article key={content.id} className="content-card">
                <div className="content-card__header">
                  <div className="stack">
                    <h3>{content.title}</h3>
                    <div className="meta-row">
                      <span>{formatDate(content.published_date)}</span>
                      <span>{content.author || "Unknown author"}</span>
                      <span>{content.source_plugin}</span>
                    </div>
                  </div>
                  <StatusBadge tone={(content.relevance_score ?? 0) >= 0.7 ? "positive" : "warning"}>
                    Relevance {formatScore(content.relevance_score)}
                  </StatusBadge>
                </div>

                <div className="chip-row">
                  <span className="chip">{content.content_type || "unclassified"}</span>
                  {content.is_reference ? <span className="chip">reference</span> : null}
                  {!content.is_active ? <span className="chip">archived</span> : null}
                </div>

                <p className="meta-copy">{truncateText(content.content_text)}</p>

                <div className="action-row">
                  <Link className="button-link" href={`/content/${content.id}?tenant=${selectedTenant.id}`}>
                    Open detail
                  </Link>
                  <form action="/api/feedback" method="POST">
                    <input type="hidden" name="tenantId" value={selectedTenant.id} />
                    <input type="hidden" name="contentId" value={content.id} />
                    <input type="hidden" name="feedbackType" value="upvote" />
                    <input type="hidden" name="redirectTo" value={`/?tenant=${selectedTenant.id}`} />
                    <button className="button" type="submit">
                      Upvote
                    </button>
                  </form>
                  <form action="/api/feedback" method="POST">
                    <input type="hidden" name="tenantId" value={selectedTenant.id} />
                    <input type="hidden" name="contentId" value={content.id} />
                    <input type="hidden" name="feedbackType" value="downvote" />
                    <input type="hidden" name="redirectTo" value={`/?tenant=${selectedTenant.id}`} />
                    <button className="ghost-button" type="submit">
                      Downvote
                    </button>
                  </form>
                </div>
              </article>
            ))}
          </div>

          <aside className="stack">
            <article className="card">
              <p className="eyebrow">Tenant focus</p>
              <h3>{selectedTenant.name}</h3>
              <p className="meta-copy">{selectedTenant.topic_description}</p>
            </article>

            <article className="card">
              <p className="eyebrow">Active sources</p>
              <p className="card-value">{sourceConfigs.filter((item) => item.is_active).length}</p>
              <p className="card-note">Configured feeds and subreddits delivering new content.</p>
            </article>

            <article className="card">
              <p className="eyebrow">Editorial queue</p>
              <p className="card-value">{pendingReviewItems.length}</p>
              <p className="card-note">Use the view switch above to resolve borderline items.</p>
            </article>
          </aside>
        </section>
      )}
    </AppShell>
  );
}