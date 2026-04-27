import "server-only"

import { cache } from "react"

import type {
  Content,
  ContentSkillName,
  Entity,
  IngestionRun,
  ReviewQueueItem,
  SkillResult,
  SourceConfig,
  Tenant,
  UserFeedback,
} from "@/lib/types"

const API_BASE_URL =
  process.env.NEWSLETTER_API_BASE_URL ?? "http://127.0.0.1:8080"

function getBasicAuthHeader() {
  const username = process.env.NEWSLETTER_API_USERNAME
  const password = process.env.NEWSLETTER_API_PASSWORD

  if (!username || !password) {
    throw new Error(
      "NEWSLETTER_API_USERNAME and NEWSLETTER_API_PASSWORD must be set for the frontend.",
    )
  }

  return `Basic ${Buffer.from(`${username}:${password}`).toString("base64")}`
}

function buildUrl(path: string) {
  return new URL(path, API_BASE_URL).toString()
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

  const text = await response.text()
  const data = text ? (JSON.parse(text) as T) : (undefined as T)
  if (!response.ok) {
    throw new Error(`API request failed (${response.status}): ${text}`)
  }
  return data
}

export const getTenants = cache(
  async (): Promise<Tenant[]> => apiFetch<Tenant[]>("/api/v1/tenants/"),
)

export async function getTenantContents(tenantId: number): Promise<Content[]> {
  return apiFetch<Content[]>(`/api/v1/tenants/${tenantId}/contents/`)
}

export async function getTenantContent(
  tenantId: number,
  contentId: number,
): Promise<Content> {
  return apiFetch<Content>(`/api/v1/tenants/${tenantId}/contents/${contentId}/`)
}

export async function getTenantEntities(tenantId: number): Promise<Entity[]> {
  return apiFetch<Entity[]>(`/api/v1/tenants/${tenantId}/entities/`)
}

export async function getTenantSkillResults(
  tenantId: number,
): Promise<SkillResult[]> {
  return apiFetch<SkillResult[]>(`/api/v1/tenants/${tenantId}/skill-results/`)
}

export async function getContentSkillResults(
  tenantId: number,
  contentId: number,
): Promise<SkillResult[]> {
  const skillResults = await getTenantSkillResults(tenantId)
  return skillResults.filter((skillResult) => skillResult.content === contentId)
}

export async function getTenantReviewQueue(
  tenantId: number,
): Promise<ReviewQueueItem[]> {
  return apiFetch<ReviewQueueItem[]>(
    `/api/v1/tenants/${tenantId}/review-queue/`,
  )
}

export async function getTenantIngestionRuns(
  tenantId: number,
): Promise<IngestionRun[]> {
  return apiFetch<IngestionRun[]>(`/api/v1/tenants/${tenantId}/ingestion-runs/`)
}

export async function getTenantSourceConfigs(
  tenantId: number,
): Promise<SourceConfig[]> {
  return apiFetch<SourceConfig[]>(`/api/v1/tenants/${tenantId}/source-configs/`)
}

export async function getTenantFeedback(
  tenantId: number,
): Promise<UserFeedback[]> {
  return apiFetch<UserFeedback[]>(`/api/v1/tenants/${tenantId}/feedback/`)
}

export async function createFeedback(
  tenantId: number,
  contentId: number,
  feedbackType: "upvote" | "downvote",
) {
  return apiFetch(`/api/v1/tenants/${tenantId}/feedback/`, {
    method: "POST",
    body: JSON.stringify({ content: contentId, feedback_type: feedbackType }),
  })
}

export async function createEntity(
  tenantId: number,
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
  return apiFetch(`/api/v1/tenants/${tenantId}/entities/`, {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function updateEntity(
  entityId: number,
  tenantId: number,
  payload: Record<string, unknown>,
) {
  return apiFetch(`/api/v1/tenants/${tenantId}/entities/${entityId}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  })
}

export async function deleteEntity(entityId: number, tenantId: number) {
  return apiFetch(`/api/v1/tenants/${tenantId}/entities/${entityId}/`, {
    method: "DELETE",
  })
}

export async function createSourceConfig(
  tenantId: number,
  payload: {
    plugin_name: string
    config: Record<string, unknown>
    is_active: boolean
  },
) {
  return apiFetch(`/api/v1/tenants/${tenantId}/source-configs/`, {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function updateSourceConfig(
  sourceConfigId: number,
  tenantId: number,
  payload: Record<string, unknown>,
) {
  return apiFetch(
    `/api/v1/tenants/${tenantId}/source-configs/${sourceConfigId}/`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
  )
}

export async function updateReviewQueueItem(
  reviewId: number,
  tenantId: number,
  payload: Record<string, unknown>,
) {
  return apiFetch(`/api/v1/tenants/${tenantId}/review-queue/${reviewId}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  })
}

export async function runContentSkill(
  tenantId: number,
  contentId: number,
  skillName: ContentSkillName,
) {
  return apiFetch<SkillResult>(
    `/api/v1/tenants/${tenantId}/contents/${contentId}/skills/${skillName}/`,
    {
      method: "POST",
    },
  )
}
