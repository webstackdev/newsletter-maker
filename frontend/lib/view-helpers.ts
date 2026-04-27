import type { HealthStatus, Tenant } from "@/lib/types"

export type SearchParams = Record<string, string | string[] | undefined>

export function getSearchParam(searchParams: SearchParams, key: string) {
  const value = searchParams[key]
  if (Array.isArray(value)) {
    return value[0] ?? ""
  }
  return value ?? ""
}

export function selectTenant(tenants: Tenant[], searchParams: SearchParams) {
  if (tenants.length === 0) {
    return null
  }

  const requestedTenantId = Number.parseInt(
    getSearchParam(searchParams, "tenant"),
    10,
  )
  const selectedTenant = tenants.find(
    (tenant) => tenant.id === requestedTenantId,
  )
  return selectedTenant ?? tenants[0]
}

export function formatDate(value: string | null) {
  if (!value) {
    return "Never"
  }
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))
}

export function formatScore(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "n/a"
  }
  return value.toFixed(2)
}

export function truncateText(value: string, maxLength = 220) {
  if (value.length <= maxLength) {
    return value
  }
  return `${value.slice(0, maxLength).trimEnd()}...`
}

export function healthTone(status: HealthStatus) {
  switch (status) {
    case "healthy":
      return "positive" as const
    case "degraded":
      return "warning" as const
    case "failing":
      return "negative" as const
    default:
      return "neutral" as const
  }
}

export function getErrorMessage(searchParams: SearchParams) {
  return getSearchParam(searchParams, "error")
}

export function getSuccessMessage(searchParams: SearchParams) {
  return getSearchParam(searchParams, "message")
}
