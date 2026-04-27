import Link from "next/link"

import { AppShell } from "@/components/app-shell"
import { StatusBadge } from "@/components/status-badge"
import {
  getTenantContents,
  getTenantEntities,
  getTenantFeedback,
  getTenantReviewQueue,
  getTenants,
  getTenantSourceConfigs,
} from "@/lib/api"
import {
  formatDate,
  formatScore,
  getErrorMessage,
  getSearchParam,
  getSuccessMessage,
  selectTenant,
  truncateText,
} from "@/lib/view-helpers"

type HomePageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}

const panelClass =
  "rounded-3xl border border-[#1f2b27]/12 bg-[rgba(255,250,244,0.86)] p-5 shadow-[0_24px_60px_rgba(35,30,22,0.12)] backdrop-blur-xl"
const eyebrowClass = "m-0 text-[0.78rem] uppercase tracking-[0.12em] opacity-70"
const emptyStateClass =
  "rounded-[18px] bg-[#1f2b27]/6 px-4 py-4 text-sm leading-6 text-[#5d6d67]"
const errorBannerClass =
  "rounded-[18px] bg-[#c55f4d]/14 px-4 py-4 text-sm leading-6 text-[#7c3023]"
const metaRowClass = "flex flex-wrap gap-2 text-sm text-[#5d6d67]"
const inputClass =
  "w-full rounded-2xl border border-[#1f2b27]/12 bg-white/70 px-4 py-3 text-[#1f2b27] outline-none transition focus:border-[#156f68]/40 focus:ring-2 focus:ring-[#156f68]/15"
const labelClass = "grid gap-2"
const labelTextClass = "text-sm font-medium text-[#1f2b27]"
const primaryButtonClass =
  "inline-flex min-h-11 items-center justify-center rounded-full bg-[linear-gradient(135deg,#156f68,#1d8d83)] px-4 py-3 text-sm font-medium text-white transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
const ghostButtonClass =
  "inline-flex min-h-11 items-center justify-center rounded-full border border-[#1f2b27]/12 bg-transparent px-4 py-3 text-sm font-medium text-[#1f2b27] transition hover:bg-white/50 disabled:cursor-not-allowed disabled:opacity-50"
const chipClass =
  "inline-flex items-center rounded-full border border-[#1f2b27]/12 bg-white/55 px-3 py-1 text-sm text-[#1f2b27]"

export default async function HomePage({ searchParams }: HomePageProps) {
  const resolvedSearchParams = await searchParams
  const tenants = await getTenants()
  const selectedTenant = selectTenant(tenants, resolvedSearchParams)

  if (!selectedTenant) {
    return (
      <AppShell
        title="Dashboard"
        description="Create a tenant in Django admin first, then come back here to review ingested content."
        tenants={[]}
        selectedTenantId={null}
      >
        <div className={emptyStateClass}>
          No tenants are available for the configured API user.
        </div>
      </AppShell>
    )
  }

  const view = getSearchParam(resolvedSearchParams, "view") || "content"
  const contentTypeFilter = getSearchParam(resolvedSearchParams, "contentType")
  const sourceFilter = getSearchParam(resolvedSearchParams, "source")
  const daysFilter = Number.parseInt(
    getSearchParam(resolvedSearchParams, "days") || "30",
    10,
  )

  const [contents, reviewQueue, entities, sourceConfigs, feedback] =
    await Promise.all([
      getTenantContents(selectedTenant.id),
      getTenantReviewQueue(selectedTenant.id),
      getTenantEntities(selectedTenant.id),
      getTenantSourceConfigs(selectedTenant.id),
      getTenantFeedback(selectedTenant.id),
    ])

  const activeContents = contents.filter((content) => content.is_active)
  const thresholdDate = new Date()
  thresholdDate.setDate(
    thresholdDate.getDate() - (Number.isNaN(daysFilter) ? 30 : daysFilter),
  )

  const filteredContents = activeContents
    .filter(
      (content) =>
        !contentTypeFilter || content.content_type === contentTypeFilter,
    )
    .filter(
      (content) => !sourceFilter || content.source_plugin === sourceFilter,
    )
    .filter((content) => new Date(content.published_date) >= thresholdDate)
    .sort((left, right) => {
      const relevanceDelta =
        (right.relevance_score ?? -1) - (left.relevance_score ?? -1)
      if (relevanceDelta !== 0) {
        return relevanceDelta
      }
      return (
        new Date(right.published_date).getTime() -
        new Date(left.published_date).getTime()
      )
    })

  const contentMap = new Map(contents.map((content) => [content.id, content]))
  const pendingReviewItems = reviewQueue.filter((item) => !item.resolved)
  const contentTypes = Array.from(
    new Set(
      activeContents.map((content) => content.content_type).filter(Boolean),
    ),
  ).sort()
  const sources = Array.from(
    new Set(activeContents.map((content) => content.source_plugin)),
  ).sort()
  const positiveFeedback = feedback.filter(
    (item) => item.feedback_type === "upvote",
  ).length
  const negativeFeedback = feedback.filter(
    (item) => item.feedback_type === "downvote",
  ).length
  const errorMessage = getErrorMessage(resolvedSearchParams)
  const successMessage = getSuccessMessage(resolvedSearchParams)

  return (
    <AppShell
      title={`${selectedTenant.name} dashboard`}
      description="Ranked content, pending human review, and quick editorial actions backed by the current Django API."
      tenants={tenants}
      selectedTenantId={selectedTenant.id}
    >
      <section className="mb-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <article className={panelClass}>
          <p className={eyebrowClass}>Surfaced</p>
          <p className="mt-1 text-3xl font-bold">{filteredContents.length}</p>
          <p className="text-sm leading-6 text-[#5d6d67]">
            Active content items in the current filter window.
          </p>
        </article>
        <article className={panelClass}>
          <p className={eyebrowClass}>Review queue</p>
          <p className="mt-1 text-3xl font-bold">{pendingReviewItems.length}</p>
          <p className="text-sm leading-6 text-[#5d6d67]">
            Borderline or low-confidence items waiting on an editor.
          </p>
        </article>
        <article className={panelClass}>
          <p className={eyebrowClass}>Tracked entities</p>
          <p className="mt-1 text-3xl font-bold">{entities.length}</p>
          <p className="text-sm leading-6 text-[#5d6d67]">
            People, vendors, and organizations linked to this tenant.
          </p>
        </article>
        <article className={panelClass}>
          <p className={eyebrowClass}>Signals</p>
          <p className="mt-1 text-3xl font-bold">
            {positiveFeedback}/{negativeFeedback}
          </p>
          <p className="text-sm leading-6 text-[#5d6d67]">
            Upvotes and downvotes captured through the API so far.
          </p>
        </article>
      </section>

      {errorMessage ? (
        <div className={errorBannerClass}>{errorMessage}</div>
      ) : null}
      {successMessage ? (
        <div className={emptyStateClass}>{successMessage}</div>
      ) : null}

      <form
        className={`${panelClass} mb-4 grid gap-4 p-[1.1rem] sm:grid-cols-2 xl:grid-cols-[repeat(auto-fit,minmax(180px,1fr))] xl:items-end`}
        method="GET"
      >
        <input type="hidden" name="tenant" value={selectedTenant.id} />
        <div className={labelClass}>
          <label className={labelTextClass} htmlFor="view">
            View
          </label>
          <select
            className={inputClass}
            id="view"
            name="view"
            defaultValue={view}
          >
            <option value="content">Surfaced content</option>
            <option value="review">Pending review</option>
          </select>
        </div>
        <div className={labelClass}>
          <label className={labelTextClass} htmlFor="contentType">
            Content type
          </label>
          <select
            className={inputClass}
            id="contentType"
            name="contentType"
            defaultValue={contentTypeFilter}
          >
            <option value="">All types</option>
            {contentTypes.map((contentType) => (
              <option key={contentType} value={contentType}>
                {contentType}
              </option>
            ))}
          </select>
        </div>
        <div className={labelClass}>
          <label className={labelTextClass} htmlFor="source">
            Source
          </label>
          <select
            className={inputClass}
            id="source"
            name="source"
            defaultValue={sourceFilter}
          >
            <option value="">All sources</option>
            {sources.map((source) => (
              <option key={source} value={source}>
                {source}
              </option>
            ))}
          </select>
        </div>
        <div className={labelClass}>
          <label className={labelTextClass} htmlFor="days">
            Published within
          </label>
          <select
            className={inputClass}
            id="days"
            name="days"
            defaultValue={String(daysFilter)}
          >
            <option value="7">7 days</option>
            <option value="14">14 days</option>
            <option value="30">30 days</option>
            <option value="90">90 days</option>
          </select>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button className={primaryButtonClass} type="submit">
            Apply filters
          </button>
          <Link
            className={ghostButtonClass}
            href={`/?tenant=${selectedTenant.id}`}
          >
            Reset
          </Link>
        </div>
      </form>

      {view === "review" ? (
        <section className={`${panelClass} overflow-hidden`}>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-[#1f2b27]/12 text-sm text-[#5d6d67]">
                  <th className="px-3 py-4 font-medium">Content</th>
                  <th className="px-3 py-4 font-medium">Reason</th>
                  <th className="px-3 py-4 font-medium">Confidence</th>
                  <th className="px-3 py-4 font-medium">Queued</th>
                  <th className="px-3 py-4 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {pendingReviewItems.length === 0 ? (
                  <tr>
                    <td className="px-3 py-4" colSpan={5}>
                      <div className={emptyStateClass}>
                        No unresolved review items for this tenant right now.
                      </div>
                    </td>
                  </tr>
                ) : null}
                {pendingReviewItems.map((item) => {
                  const content = contentMap.get(item.content)
                  return (
                    <tr
                      key={item.id}
                      className="border-b border-[#1f2b27]/12 align-top last:border-b-0"
                    >
                      <td className="px-3 py-4">
                        <strong className="font-medium text-[#1f2b27]">
                          {content?.title ?? `Content #${item.content}`}
                        </strong>
                        <div className={`${metaRowClass} mt-2`}>
                          <span>
                            {content?.source_plugin ?? "unknown source"}
                          </span>
                          <span>{content?.content_type || "unclassified"}</span>
                        </div>
                      </td>
                      <td className="px-3 py-4 text-sm text-[#1f2b27]">
                        {item.reason}
                      </td>
                      <td className="px-3 py-4 text-sm text-[#1f2b27]">
                        {formatScore(item.confidence)}
                      </td>
                      <td className="px-3 py-4 text-sm text-[#1f2b27]">
                        {formatDate(item.created_at)}
                      </td>
                      <td className="px-3 py-4">
                        <div className="flex flex-wrap items-center gap-3">
                          <form action={`/api/review/${item.id}`} method="POST">
                            <input
                              type="hidden"
                              name="tenantId"
                              value={selectedTenant.id}
                            />
                            <input type="hidden" name="resolved" value="true" />
                            <input
                              type="hidden"
                              name="resolution"
                              value="human_approved"
                            />
                            <input
                              type="hidden"
                              name="redirectTo"
                              value={`/?tenant=${selectedTenant.id}&view=review`}
                            />
                            <button
                              className={primaryButtonClass}
                              type="submit"
                            >
                              Approve
                            </button>
                          </form>
                          <form action={`/api/review/${item.id}`} method="POST">
                            <input
                              type="hidden"
                              name="tenantId"
                              value={selectedTenant.id}
                            />
                            <input type="hidden" name="resolved" value="true" />
                            <input
                              type="hidden"
                              name="resolution"
                              value="human_rejected"
                            />
                            <input
                              type="hidden"
                              name="redirectTo"
                              value={`/?tenant=${selectedTenant.id}&view=review`}
                            />
                            <button className={ghostButtonClass} type="submit">
                              Reject
                            </button>
                          </form>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        <section className="grid gap-4 xl:grid-cols-[minmax(0,1.65fr)_minmax(280px,0.95fr)]">
          <div className="space-y-4">
            {filteredContents.length === 0 ? (
              <div className={emptyStateClass}>
                No content matched the current filters.
              </div>
            ) : null}
            {filteredContents.map((content) => (
              <article key={content.id} className={`${panelClass} grid gap-4`}>
                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                  <div className="space-y-3">
                    <h3 className="font-[family:var(--font-display)] text-[1.45rem] font-bold">
                      {content.title}
                    </h3>
                    <div className={metaRowClass}>
                      <span>{formatDate(content.published_date)}</span>
                      <span>{content.author || "Unknown author"}</span>
                      <span>{content.source_plugin}</span>
                    </div>
                  </div>
                  <StatusBadge
                    tone={
                      (content.relevance_score ?? 0) >= 0.7
                        ? "positive"
                        : "warning"
                    }
                  >
                    Relevance {formatScore(content.relevance_score)}
                  </StatusBadge>
                </div>

                <div className="flex flex-wrap gap-2">
                  <span className={chipClass}>
                    {content.content_type || "unclassified"}
                  </span>
                  {content.is_reference ? (
                    <span className={chipClass}>reference</span>
                  ) : null}
                  {!content.is_active ? (
                    <span className={chipClass}>archived</span>
                  ) : null}
                </div>

                <p className="text-sm leading-6 text-[#5d6d67]">
                  {truncateText(content.content_text)}
                </p>

                <div className="flex flex-wrap items-center gap-3">
                  <Link
                    className={primaryButtonClass}
                    href={`/content/${content.id}?tenant=${selectedTenant.id}`}
                  >
                    Open detail
                  </Link>
                  <form action="/api/feedback" method="POST">
                    <input
                      type="hidden"
                      name="tenantId"
                      value={selectedTenant.id}
                    />
                    <input type="hidden" name="contentId" value={content.id} />
                    <input type="hidden" name="feedbackType" value="upvote" />
                    <input
                      type="hidden"
                      name="redirectTo"
                      value={`/?tenant=${selectedTenant.id}`}
                    />
                    <button className={primaryButtonClass} type="submit">
                      Upvote
                    </button>
                  </form>
                  <form action="/api/feedback" method="POST">
                    <input
                      type="hidden"
                      name="tenantId"
                      value={selectedTenant.id}
                    />
                    <input type="hidden" name="contentId" value={content.id} />
                    <input type="hidden" name="feedbackType" value="downvote" />
                    <input
                      type="hidden"
                      name="redirectTo"
                      value={`/?tenant=${selectedTenant.id}`}
                    />
                    <button className={ghostButtonClass} type="submit">
                      Downvote
                    </button>
                  </form>
                </div>
              </article>
            ))}
          </div>

          <aside className="space-y-4">
            <article className={panelClass}>
              <p className={eyebrowClass}>Tenant focus</p>
              <h3 className="font-[family:var(--font-display)] text-[1.45rem] font-bold">
                {selectedTenant.name}
              </h3>
              <p className="text-sm leading-6 text-[#5d6d67]">
                {selectedTenant.topic_description}
              </p>
            </article>

            <article className={panelClass}>
              <p className={eyebrowClass}>Active sources</p>
              <p className="mt-1 text-3xl font-bold">
                {sourceConfigs.filter((item) => item.is_active).length}
              </p>
              <p className="text-sm leading-6 text-[#5d6d67]">
                Configured feeds and subreddits delivering new content.
              </p>
            </article>

            <article className={panelClass}>
              <p className={eyebrowClass}>Editorial queue</p>
              <p className="mt-1 text-3xl font-bold">
                {pendingReviewItems.length}
              </p>
              <p className="text-sm leading-6 text-[#5d6d67]">
                Use the view switch above to resolve borderline items.
              </p>
            </article>
          </aside>
        </section>
      )}
    </AppShell>
  )
}
