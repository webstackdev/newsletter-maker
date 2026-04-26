import { AppShell } from "@/components/app-shell"
import { StatusBadge } from "@/components/status-badge"
import {
  getTenantIngestionRuns,
  getTenants,
  getTenantSourceConfigs,
} from "@/lib/api"
import type { HealthStatus } from "@/lib/types"
import { formatDate, healthTone, selectTenant } from "@/lib/view-helpers"

type HealthPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}

const panelClass =
  "rounded-3xl border border-[#1f2b27]/12 bg-[rgba(255,250,244,0.86)] p-5 shadow-[0_24px_60px_rgba(35,30,22,0.12)] backdrop-blur-xl"
const emptyStateClass =
  "rounded-[18px] bg-[#1f2b27]/6 px-4 py-4 text-sm leading-6 text-[#5d6d67]"
const metaRowClass = "mt-2 flex flex-wrap gap-2 text-sm text-[#5d6d67]"

function deriveSourceStatus(
  isActive: boolean,
  latestRunStatus: string | null,
  lastFetchedAt: string | null,
): HealthStatus {
  if (!isActive) {
    return "idle"
  }
  if (latestRunStatus === "failed") {
    return "failing"
  }
  if (latestRunStatus === "running") {
    return "degraded"
  }
  if (!lastFetchedAt) {
    return "degraded"
  }
  return "healthy"
}

export default async function HealthPage({ searchParams }: HealthPageProps) {
  const resolvedSearchParams = await searchParams
  const tenants = await getTenants()
  const selectedTenant = selectTenant(tenants, resolvedSearchParams)

  if (!selectedTenant) {
    return (
      <AppShell
        title="Health"
        description="No tenant found for this API user."
        tenants={[]}
        selectedTenantId={null}
      >
        <div className={emptyStateClass}>
          Create a tenant first in Django admin.
        </div>
      </AppShell>
    )
  }

  const [sourceConfigs, ingestionRuns] = await Promise.all([
    getTenantSourceConfigs(selectedTenant.id),
    getTenantIngestionRuns(selectedTenant.id),
  ])

  const latestRunByPlugin = new Map<string, (typeof ingestionRuns)[number]>()
  for (const ingestionRun of ingestionRuns) {
    if (!latestRunByPlugin.has(ingestionRun.plugin_name)) {
      latestRunByPlugin.set(ingestionRun.plugin_name, ingestionRun)
    }
  }

  return (
    <AppShell
      title="Ingestion health"
      description="A source-by-source view of freshness, last run outcome, and whether the pipeline is idle, healthy, or failing."
      tenants={tenants}
      selectedTenantId={selectedTenant.id}
    >
      <section className={`${panelClass} overflow-hidden`}>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-[#1f2b27]/12 text-sm text-[#5d6d67]">
                <th className="px-3 py-4 font-medium">Source</th>
                <th className="px-3 py-4 font-medium">Status</th>
                <th className="px-3 py-4 font-medium">Last fetch</th>
                <th className="px-3 py-4 font-medium">Latest run</th>
                <th className="px-3 py-4 font-medium">Items</th>
                <th className="px-3 py-4 font-medium">Errors</th>
              </tr>
            </thead>
            <tbody>
              {sourceConfigs.length === 0 ? (
                <tr>
                  <td className="px-3 py-4" colSpan={6}>
                    <div className={emptyStateClass}>
                      No source configurations exist for this tenant yet.
                    </div>
                  </td>
                </tr>
              ) : null}
              {sourceConfigs.map((sourceConfig) => {
                const latestRun =
                  latestRunByPlugin.get(sourceConfig.plugin_name) ?? null
                const status = deriveSourceStatus(
                  sourceConfig.is_active,
                  latestRun?.status ?? null,
                  sourceConfig.last_fetched_at,
                )
                return (
                  <tr
                    key={sourceConfig.id}
                    className="border-b border-[#1f2b27]/12 align-top last:border-b-0"
                  >
                    <td className="px-3 py-4">
                      <strong className="font-medium text-[#1f2b27]">
                        {sourceConfig.plugin_name}
                      </strong>
                      <div className={metaRowClass}>
                        <span>Config #{sourceConfig.id}</span>
                        <span>
                          {sourceConfig.is_active ? "active" : "disabled"}
                        </span>
                      </div>
                    </td>
                    <td className="px-3 py-4">
                      <StatusBadge tone={healthTone(status)}>
                        {status}
                      </StatusBadge>
                    </td>
                    <td className="px-3 py-4 text-sm text-[#1f2b27]">
                      {formatDate(sourceConfig.last_fetched_at)}
                    </td>
                    <td className="px-3 py-4 text-sm text-[#1f2b27]">
                      {latestRun
                        ? `${latestRun.status} at ${formatDate(latestRun.started_at)}`
                        : "No runs yet"}
                    </td>
                    <td className="px-3 py-4 text-sm text-[#1f2b27]">
                      {latestRun
                        ? `${latestRun.items_ingested}/${latestRun.items_fetched}`
                        : "0/0"}
                    </td>
                    <td className="px-3 py-4 text-sm text-[#1f2b27]">
                      {latestRun?.error_message || "-"}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>
    </AppShell>
  )
}
