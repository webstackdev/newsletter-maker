import { AppShell } from "@/components/app-shell";
import { StatusBadge } from "@/components/status-badge";
import { getTenantIngestionRuns, getTenantSourceConfigs, getTenants } from "@/lib/api";
import type { HealthStatus } from "@/lib/types";
import { formatDate, healthTone, selectTenant } from "@/lib/view-helpers";

type HealthPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

function deriveSourceStatus(isActive: boolean, latestRunStatus: string | null, lastFetchedAt: string | null): HealthStatus {
  if (!isActive) {
    return "idle";
  }
  if (latestRunStatus === "failed") {
    return "failing";
  }
  if (latestRunStatus === "running") {
    return "degraded";
  }
  if (!lastFetchedAt) {
    return "degraded";
  }
  return "healthy";
}

export default async function HealthPage({ searchParams }: HealthPageProps) {
  const resolvedSearchParams = await searchParams;
  const tenants = await getTenants();
  const selectedTenant = selectTenant(tenants, resolvedSearchParams);

  if (!selectedTenant) {
    return (
      <AppShell title="Health" description="No tenant found for this API user." tenants={[]} selectedTenantId={null}>
        <div className="empty-state">Create a tenant first in Django admin.</div>
      </AppShell>
    );
  }

  const [sourceConfigs, ingestionRuns] = await Promise.all([
    getTenantSourceConfigs(selectedTenant.id),
    getTenantIngestionRuns(selectedTenant.id),
  ]);

  const latestRunByPlugin = new Map<string, (typeof ingestionRuns)[number]>();
  for (const ingestionRun of ingestionRuns) {
    if (!latestRunByPlugin.has(ingestionRun.plugin_name)) {
      latestRunByPlugin.set(ingestionRun.plugin_name, ingestionRun);
    }
  }

  return (
    <AppShell
      title="Ingestion health"
      description="A source-by-source view of freshness, last run outcome, and whether the pipeline is idle, healthy, or failing."
      tenants={tenants}
      selectedTenantId={selectedTenant.id}
    >
      <section className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Source</th>
              <th>Status</th>
              <th>Last fetch</th>
              <th>Latest run</th>
              <th>Items</th>
              <th>Errors</th>
            </tr>
          </thead>
          <tbody>
            {sourceConfigs.length === 0 ? (
              <tr>
                <td colSpan={6}>
                  <div className="empty-state">No source configurations exist for this tenant yet.</div>
                </td>
              </tr>
            ) : null}
            {sourceConfigs.map((sourceConfig) => {
              const latestRun = latestRunByPlugin.get(sourceConfig.plugin_name) ?? null;
              const status = deriveSourceStatus(sourceConfig.is_active, latestRun?.status ?? null, sourceConfig.last_fetched_at);
              return (
                <tr key={sourceConfig.id}>
                  <td>
                    <strong>{sourceConfig.plugin_name}</strong>
                    <div className="meta-row">
                      <span>Config #{sourceConfig.id}</span>
                      <span>{sourceConfig.is_active ? "active" : "disabled"}</span>
                    </div>
                  </td>
                  <td>
                    <StatusBadge tone={healthTone(status)}>{status}</StatusBadge>
                  </td>
                  <td>{formatDate(sourceConfig.last_fetched_at)}</td>
                  <td>{latestRun ? `${latestRun.status} at ${formatDate(latestRun.started_at)}` : "No runs yet"}</td>
                  <td>
                    {latestRun ? `${latestRun.items_ingested}/${latestRun.items_fetched}` : "0/0"}
                  </td>
                  <td>{latestRun?.error_message || "-"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </AppShell>
  );
}