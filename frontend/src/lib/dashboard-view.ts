import type { Content, ReviewQueueItem, UserFeedback } from "@/lib/types"
import { getSearchParam, type SearchParams } from "@/lib/view-helpers"

export type DashboardView = "content" | "review"

type BuildDashboardViewArgs = {
  contents: Content[]
  reviewQueue: ReviewQueueItem[]
  feedback: UserFeedback[]
  searchParams: SearchParams
  now?: Date
}

export function buildDashboardView({
  contents,
  reviewQueue,
  feedback,
  searchParams,
  now = new Date(),
}: BuildDashboardViewArgs) {
  const requestedView = getSearchParam(searchParams, "view")
  const view: DashboardView = requestedView === "review" ? "review" : "content"
  const contentTypeFilter = getSearchParam(searchParams, "contentType")
  const sourceFilter = getSearchParam(searchParams, "source")
  const parsedDaysFilter = Number.parseInt(
    getSearchParam(searchParams, "days") || "30",
    10,
  )
  const daysFilter = Number.isNaN(parsedDaysFilter) ? 30 : parsedDaysFilter

  const activeContents = contents.filter((content) => content.is_active)
  const thresholdDate = new Date(now)
  thresholdDate.setDate(thresholdDate.getDate() - daysFilter)

  const filteredContents = activeContents
    .filter(
      (content) =>
        !contentTypeFilter || content.content_type === contentTypeFilter,
    )
    .filter((content) => !sourceFilter || content.source_plugin === sourceFilter)
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

  return {
    contentMap,
    contentTypeFilter,
    contentTypes,
    daysFilter,
    filteredContents,
    negativeFeedback,
    pendingReviewItems,
    positiveFeedback,
    sourceFilter,
    sources,
    view,
  }
}
