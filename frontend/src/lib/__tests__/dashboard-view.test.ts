import { describe, expect, it } from "vitest"

import { buildDashboardView } from "@/lib/dashboard-view"
import type { Content, ReviewQueueItem, UserFeedback } from "@/lib/types"

const contents: Content[] = [
  {
    id: 1,
    project: 3,
    url: "https://example.com/post-1",
    title: "Most relevant",
    author: "A",
    entity: null,
    source_plugin: "rss",
    content_type: "article",
    published_date: "2026-04-27T12:00:00Z",
    ingested_at: "2026-04-27T12:10:00Z",
    content_text: "Alpha",
    relevance_score: 0.9,
    embedding_id: "emb-1",
    is_reference: false,
    is_active: true,
  },
  {
    id: 2,
    project: 3,
    url: "https://example.com/post-2",
    title: "Tie breaker by recency",
    author: "B",
    entity: null,
    source_plugin: "reddit",
    content_type: "article",
    published_date: "2026-04-26T12:00:00Z",
    ingested_at: "2026-04-26T12:10:00Z",
    content_text: "Beta",
    relevance_score: 0.8,
    embedding_id: "emb-2",
    is_reference: false,
    is_active: true,
  },
  {
    id: 3,
    project: 3,
    url: "https://example.com/post-3",
    title: "Same score older date",
    author: "C",
    entity: null,
    source_plugin: "reddit",
    content_type: "tutorial",
    published_date: "2026-04-20T12:00:00Z",
    ingested_at: "2026-04-20T12:10:00Z",
    content_text: "Gamma",
    relevance_score: 0.8,
    embedding_id: "emb-3",
    is_reference: false,
    is_active: true,
  },
  {
    id: 4,
    project: 3,
    url: "https://example.com/post-4",
    title: "Old and inactive",
    author: "D",
    entity: null,
    source_plugin: "rss",
    content_type: "article",
    published_date: "2026-02-01T12:00:00Z",
    ingested_at: "2026-02-01T12:10:00Z",
    content_text: "Delta",
    relevance_score: 1,
    embedding_id: "emb-4",
    is_reference: false,
    is_active: false,
  },
]

const reviewQueue: ReviewQueueItem[] = [
  {
    id: 11,
    project: 3,
    content: 2,
    reason: "borderline_relevance",
    confidence: 0.52,
    created_at: "2026-04-27T15:00:00Z",
    resolved: false,
    resolution: "",
  },
  {
    id: 12,
    project: 3,
    content: 3,
    reason: "low_confidence_classification",
    confidence: 0.44,
    created_at: "2026-04-27T16:00:00Z",
    resolved: true,
    resolution: "human_approved",
  },
]

const feedback: UserFeedback[] = [
  {
    id: 21,
    content: 1,
    project: 3,
    user: 1,
    feedback_type: "upvote",
    created_at: "2026-04-27T12:00:00Z",
  },
  {
    id: 22,
    content: 2,
    project: 3,
    user: 1,
    feedback_type: "downvote",
    created_at: "2026-04-27T13:00:00Z",
  },
]

describe("buildDashboardView", () => {
  it("filters active content, defaults invalid days to 30, and sorts by relevance then recency", () => {
    const result = buildDashboardView({
      contents,
      reviewQueue,
      feedback,
      searchParams: { days: "not-a-number" },
      now: new Date("2026-04-28T00:00:00Z"),
    })

    expect(result.daysFilter).toBe(30)
    expect(result.view).toBe("content")
    expect(result.filteredContents.map((content) => content.id)).toEqual([1, 2, 3])
  })

  it("applies content type and source filters", () => {
    const result = buildDashboardView({
      contents,
      reviewQueue,
      feedback,
      searchParams: { contentType: "article", source: "reddit", view: "review" },
      now: new Date("2026-04-28T00:00:00Z"),
    })

    expect(result.view).toBe("review")
    expect(result.filteredContents.map((content) => content.id)).toEqual([2])
  })

  it("computes pending review items, feedback counts, content types, and sources", () => {
    const result = buildDashboardView({
      contents,
      reviewQueue,
      feedback,
      searchParams: {},
      now: new Date("2026-04-28T00:00:00Z"),
    })

    expect(result.pendingReviewItems.map((item) => item.id)).toEqual([11])
    expect(result.positiveFeedback).toBe(1)
    expect(result.negativeFeedback).toBe(1)
    expect(result.contentTypes).toEqual(["article", "tutorial"])
    expect(result.sources).toEqual(["reddit", "rss"])
    expect(result.contentMap.get(2)?.title).toBe("Tie breaker by recency")
  })
})
