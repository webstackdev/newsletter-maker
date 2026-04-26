import Link from "next/link"

import { AppShell } from "@/components/app-shell"
import { StatusBadge } from "@/components/status-badge"
import {
  getTenantContent,
  getTenantFeedback,
  getTenantReviewQueue,
  getTenants,
  getTenantSkillResults,
} from "@/lib/api"
import {
  formatDate,
  formatScore,
  getErrorMessage,
  getSuccessMessage,
  selectTenant,
} from "@/lib/view-helpers"

type ContentDetailPageProps = {
  params: Promise<{ id: string }>
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
const primaryButtonClass =
  "inline-flex min-h-11 items-center justify-center rounded-full bg-[linear-gradient(135deg,#156f68,#1d8d83)] px-4 py-3 text-sm font-medium text-white transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
const ghostButtonClass =
  "inline-flex min-h-11 items-center justify-center rounded-full border border-[#1f2b27]/12 bg-transparent px-4 py-3 text-sm font-medium text-[#1f2b27] transition hover:bg-white/50 disabled:cursor-not-allowed disabled:opacity-50"

export default async function ContentDetailPage({
  params,
  searchParams,
}: ContentDetailPageProps) {
  const [{ id }, resolvedSearchParams] = await Promise.all([
    params,
    searchParams,
  ])
  const tenants = await getTenants()
  const selectedTenant = selectTenant(tenants, resolvedSearchParams)

  if (!selectedTenant) {
    return (
      <AppShell
        title="Content detail"
        description="No tenant is available for the configured API user."
        tenants={[]}
        selectedTenantId={null}
      >
        <div className={emptyStateClass}>
          Create a tenant first in Django admin.
        </div>
      </AppShell>
    )
  }

  const contentId = Number.parseInt(id, 10)
  const [content, skillResults, reviewQueue, feedback] = await Promise.all([
    getTenantContent(selectedTenant.id, contentId),
    getTenantSkillResults(selectedTenant.id),
    getTenantReviewQueue(selectedTenant.id),
    getTenantFeedback(selectedTenant.id),
  ])
  const errorMessage = getErrorMessage(resolvedSearchParams)
  const successMessage = getSuccessMessage(resolvedSearchParams)
  const contentSkillResults = skillResults.filter(
    (item) => item.content === content.id,
  )
  const reviewItems = reviewQueue.filter((item) => item.content === content.id)
  const contentFeedback = feedback.filter((item) => item.content === content.id)
  const upvotes = contentFeedback.filter(
    (item) => item.feedback_type === "upvote",
  ).length
  const downvotes = contentFeedback.filter(
    (item) => item.feedback_type === "downvote",
  ).length
  const canSummarize = (content.relevance_score ?? 0) >= 0.7

  return (
    <AppShell
      title="Content detail"
      description="Inspect the raw article, persisted skill outputs, and editorial status for a single content item."
      tenants={tenants}
      selectedTenantId={selectedTenant.id}
    >
      {errorMessage ? (
        <div className={errorBannerClass}>{errorMessage}</div>
      ) : null}
      {successMessage ? (
        <div className={emptyStateClass}>{successMessage}</div>
      ) : null}
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.65fr)_minmax(280px,0.95fr)]">
        <div className="space-y-4">
          <article className={panelClass}>
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
              <div className="space-y-3">
                <p className={eyebrowClass}>{content.source_plugin}</p>
                <h3 className="font-[family:var(--font-display)] text-[1.45rem] font-bold">
                  {content.title}
                </h3>
                <div className={metaRowClass}>
                  <span>{formatDate(content.published_date)}</span>
                  <span>{content.author || "Unknown author"}</span>
                  <span>{content.content_type || "unclassified"}</span>
                </div>
              </div>
              <StatusBadge
                tone={
                  (content.relevance_score ?? 0) >= 0.7 ? "positive" : "warning"
                }
              >
                Relevance {formatScore(content.relevance_score)}
              </StatusBadge>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-3">
              <Link
                className={primaryButtonClass}
                href={content.url}
                target="_blank"
              >
                Open source
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
                  value={`/content/${content.id}?tenant=${selectedTenant.id}`}
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
                  value={`/content/${content.id}?tenant=${selectedTenant.id}`}
                />
                <button className={ghostButtonClass} type="submit">
                  Downvote
                </button>
              </form>
            </div>

            <div className="mt-4 whitespace-pre-wrap text-sm leading-7 text-[#5d6d67] md:text-base">
              {content.content_text}
            </div>
          </article>

          <article className={`${panelClass} space-y-4`}>
            <p className={eyebrowClass}>Skill action bar</p>
            <div className="flex flex-wrap items-center gap-3">
              <form action="/api/skills/summarization" method="POST">
                <input
                  type="hidden"
                  name="tenantId"
                  value={selectedTenant.id}
                />
                <input type="hidden" name="contentId" value={content.id} />
                <input
                  type="hidden"
                  name="redirectTo"
                  value={`/content/${content.id}?tenant=${selectedTenant.id}`}
                />
                <button
                  className={ghostButtonClass}
                  type="submit"
                  disabled={!canSummarize}
                >
                  Summarize
                </button>
              </form>
              <form action="/api/skills/relevance_scoring" method="POST">
                <input
                  type="hidden"
                  name="tenantId"
                  value={selectedTenant.id}
                />
                <input type="hidden" name="contentId" value={content.id} />
                <input
                  type="hidden"
                  name="redirectTo"
                  value={`/content/${content.id}?tenant=${selectedTenant.id}`}
                />
                <button className={ghostButtonClass} type="submit">
                  Explain relevance
                </button>
              </form>
              <form action="/api/skills/find_related" method="POST">
                <input
                  type="hidden"
                  name="tenantId"
                  value={selectedTenant.id}
                />
                <input type="hidden" name="contentId" value={content.id} />
                <input
                  type="hidden"
                  name="redirectTo"
                  value={`/content/${content.id}?tenant=${selectedTenant.id}`}
                />
                <button className={ghostButtonClass} type="submit">
                  Find related
                </button>
              </form>
            </div>
            <p className="text-sm leading-6 text-[#5d6d67]">
              These controls create new persisted SkillResult records.
              Summarization is only available once a content item has reached a
              relevance score of at least 0.70.
            </p>
          </article>

          {contentSkillResults.map((skillResult) => (
            <article key={skillResult.id} className={`${panelClass} space-y-4`}>
              <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div>
                  <p className={eyebrowClass}>{skillResult.skill_name}</p>
                  <h3 className="font-[family:var(--font-display)] text-[1.45rem] font-bold">
                    {skillResult.status}
                  </h3>
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
              <div className={metaRowClass}>
                <span>Created {formatDate(skillResult.created_at)}</span>
                <span>Latency {skillResult.latency_ms ?? 0} ms</span>
                <span>Confidence {formatScore(skillResult.confidence)}</span>
              </div>
              {skillResult.error_message ? (
                <div className={errorBannerClass}>
                  {skillResult.error_message}
                </div>
              ) : null}
              <pre className="overflow-auto rounded-2xl bg-[rgba(20,31,28,0.94)] p-4 text-sm text-[#f7f0e7]">
                {JSON.stringify(skillResult.result_data, null, 2)}
              </pre>
            </article>
          ))}
        </div>

        <aside className="space-y-4">
          <article className={panelClass}>
            <p className={eyebrowClass}>Feedback</p>
            <p className="mt-1 text-3xl font-bold">
              {upvotes}/{downvotes}
            </p>
            <p className="text-sm leading-6 text-[#5d6d67]">
              Upvotes and downvotes recorded for this item.
            </p>
          </article>

          <article className={`${panelClass} space-y-4`}>
            <p className={eyebrowClass}>Review state</p>
            {reviewItems.length === 0 ? (
              <p className="text-sm leading-6 text-[#5d6d67]">
                No review flags are attached to this content.
              </p>
            ) : null}
            {reviewItems.map((item) => (
              <div key={item.id} className="space-y-3">
                <StatusBadge tone={item.resolved ? "neutral" : "warning"}>
                  {item.reason}
                </StatusBadge>
                <p className="text-sm leading-6 text-[#5d6d67]">
                  Confidence {formatScore(item.confidence)}
                </p>
                <p className="text-sm leading-6 text-[#5d6d67]">
                  {item.resolved
                    ? item.resolution || "resolved"
                    : "Awaiting human resolution"}
                </p>
              </div>
            ))}
          </article>

          <article className={`${panelClass} space-y-4`}>
            <p className={eyebrowClass}>Navigate</p>
            <Link
              className={primaryButtonClass}
              href={`/?tenant=${selectedTenant.id}`}
            >
              Back to dashboard
            </Link>
            <Link
              className={ghostButtonClass}
              href={`/entities?tenant=${selectedTenant.id}`}
            >
              Manage entities
            </Link>
          </article>
        </aside>
      </section>
    </AppShell>
  )
}
