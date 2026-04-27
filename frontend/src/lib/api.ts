import "server-only"

import { cache } from "react"

import type {
  Content,
  ContentSkillName,
  Entity,
  IngestionRun,
  Project,
  ReviewQueueItem,
  SkillResult,
  SourceConfig,
  UserFeedback,
} from "@/lib/types"

const API_BASE_URL =
  process.env.NEWSLETTER_API_BASE_URL ?? "http://127.0.0.1:8080"

function getBasicAuthHeader() {
  const username = process.env.NEWSLETTER_API_USERNAME
  const password = process.env.NEWSLETTER_API_PASSWORD

  if (!username || !password) {
    throw new Error(
      "NEWSLETTER_API_USERNAME and NEWSLETTER_API_PASSWORD must be set for the frontend. Copy frontend/.env.example to frontend/.env.local when running Next.js outside Docker.",
    )
  }

  return `Basic ${Buffer.from(`${username}:${password}`).toString("base64")}`
}

function buildUrl(path: string) {
  return new URL(path, API_BASE_URL).toString()
}

function previewResponseBody(text: string) {
  return text.replace(/\s+/g, " ").trim().slice(0, 240)
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(buildUrl(path), {
    ...init,
    headers: {
      Authorization: getBasicAuthHeader(),
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  })

  if (response.status === 204) {
    return undefined as T
  }

  const contentType = response.headers.get("content-type") ?? ""
  const text = await response.text()
  if (!response.ok) {
    throw new Error(
      `API request failed (${response.status}) from ${buildUrl(path)} with ${contentType || "unknown content type"}: ${previewResponseBody(text)}`,
    )
  }

  if (!text) {
    return undefined as T
  }

  if (!contentType.includes("json")) {
    throw new Error(
      `API request to ${buildUrl(path)} returned ${contentType || "unknown content type"} instead of JSON: ${previewResponseBody(text)}`,
    )
  }

  try {
    return JSON.parse(text) as T
  } catch {
    throw new Error(
      `API request to ${buildUrl(path)} returned invalid JSON: ${previewResponseBody(text)}`,
    )
  }
}

export const getProjects = cache(
  async (): Promise<Project[]> => apiFetch<Project[]>("/api/v1/projects/"),
)

export async function getProjectContents(projectId: number): Promise<Content[]> {
  return apiFetch<Content[]>(`/api/v1/projects/${projectId}/contents/`)
}

export async function getProjectContent(
  projectId: number,
  contentId: number,
): Promise<Content> {
  return apiFetch<Content>(`/api/v1/projects/${projectId}/contents/${contentId}/`)
}

export async function getProjectEntities(projectId: number): Promise<Entity[]> {
  return apiFetch<Entity[]>(`/api/v1/projects/${projectId}/entities/`)
}

export async function getProjectSkillResults(
  projectId: number,
): Promise<SkillResult[]> {
  return apiFetch<SkillResult[]>(`/api/v1/projects/${projectId}/skill-results/`)
}

export async function getContentSkillResults(
  projectId: number,
  contentId: number,
): Promise<SkillResult[]> {
  const skillResults = await getProjectSkillResults(projectId)
  return skillResults.filter((skillResult) => skillResult.content === contentId)
}

export async function getProjectReviewQueue(
  projectId: number,
): Promise<ReviewQueueItem[]> {
  return apiFetch<ReviewQueueItem[]>(
    `/api/v1/projects/${projectId}/review-queue/`,
  )
}

export async function getProjectIngestionRuns(
  projectId: number,
): Promise<IngestionRun[]> {
  return apiFetch<IngestionRun[]>(`/api/v1/projects/${projectId}/ingestion-runs/`)
}

export async function getProjectSourceConfigs(
  projectId: number,
): Promise<SourceConfig[]> {
  return apiFetch<SourceConfig[]>(`/api/v1/projects/${projectId}/source-configs/`)
}

export async function getProjectFeedback(
  projectId: number,
): Promise<UserFeedback[]> {
  return apiFetch<UserFeedback[]>(`/api/v1/projects/${projectId}/feedback/`)
}

export async function createFeedback(
  projectId: number,
  contentId: number,
  feedbackType: "upvote" | "downvote",
) {
  return apiFetch(`/api/v1/projects/${projectId}/feedback/`, {
    method: "POST",
    body: JSON.stringify({ content: contentId, feedback_type: feedbackType }),
  })
}

export async function createEntity(
  projectId: number,
  payload: {
    name: string
    type: string
    description: string
    website_url: string
    github_url: string
    linkedin_url: string
    bluesky_handle: string
    mastodon_handle: string
    twitter_handle: string
  },
) {
  return apiFetch(`/api/v1/projects/${projectId}/entities/`, {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function updateEntity(
  entityId: number,
  projectId: number,
  payload: Record<string, unknown>,
) {
  return apiFetch(`/api/v1/projects/${projectId}/entities/${entityId}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  })
}

export async function deleteEntity(entityId: number, projectId: number) {
  return apiFetch(`/api/v1/projects/${projectId}/entities/${entityId}/`, {
    method: "DELETE",
  })
}

export async function createSourceConfig(
  projectId: number,
  payload: {
    plugin_name: string
    config: Record<string, unknown>
    is_active: boolean
  },
) {
  return apiFetch(`/api/v1/projects/${projectId}/source-configs/`, {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function updateSourceConfig(
  sourceConfigId: number,
  projectId: number,
  payload: Record<string, unknown>,
) {
  return apiFetch(
    `/api/v1/projects/${projectId}/source-configs/${sourceConfigId}/`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
  )
}

export async function updateReviewQueueItem(
  reviewId: number,
  projectId: number,
  payload: Record<string, unknown>,
) {
  return apiFetch(`/api/v1/projects/${projectId}/review-queue/${reviewId}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  })
}

export async function runContentSkill(
  projectId: number,
  contentId: number,
  skillName: ContentSkillName,
) {
  return apiFetch<SkillResult>(
    `/api/v1/projects/${projectId}/contents/${contentId}/skills/${skillName}/`,
    {
      method: "POST",
    },
  )
}
