import { AppShell } from "@/components/app-shell";
import { StatusBadge } from "@/components/status-badge";
import { getTenantIngestionRuns, getTenantSourceConfigs, getTenants } from "@/lib/api";
import { formatDate, getErrorMessage, getSuccessMessage, selectTenant } from "@/lib/view-helpers";

type SourcesPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function SourcesPage({ searchParams }: SourcesPageProps) {
  const resolvedSearchParams = await searchParams;
  const tenants = await getTenants();
  const selectedTenant = selectTenant(tenants, resolvedSearchParams);

  if (!selectedTenant) {
    return (
      <AppShell title="Sources" description="No tenant found for this API user." tenants={[]} selectedTenantId={null}>
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

  const errorMessage = getErrorMessage(resolvedSearchParams);
  const successMessage = getSuccessMessage(resolvedSearchParams);

  return (
    <AppShell
      title="Source configuration"
      description="Add, tune, and disable RSS feeds or Reddit subscriptions without leaving the editor dashboard."
      tenants={tenants}
      selectedTenantId={selectedTenant.id}
    >
      {errorMessage ? <div className="error-banner">{errorMessage}</div> : null}
      {successMessage ? <div className="empty-state">{successMessage}</div> : null}

      <section className="content-grid">
        <article className="form-card stack">
          <p className="eyebrow">Add source</p>
          <form className="stack" action="/api/source-configs" method="POST">
            <input type="hidden" name="tenantId" value={selectedTenant.id} />
            <input type="hidden" name="redirectTo" value={`/admin/sources?tenant=${selectedTenant.id}`} />
            <label className="field">
              <span>Plugin</span>
              <select name="plugin_name" defaultValue="rss">
                <option value="rss">RSS</option>
                <option value="reddit">Reddit</option>
              </select>
            </label>
            <label className="field">
              <span>Config JSON</span>
              <textarea
                name="config_json"
                defaultValue={JSON.stringify({ feed_url: "https://example.com/feed.xml" }, null, 2)}
              />
            </label>
            <label className="field">
              <span>Active</span>
              <select name="is_active" defaultValue="true">
                <option value="true">Active</option>
                <option value="false">Disabled</option>
              </select>
            </label>
            <button className="button" type="submit">
              Create source
            </button>
          </form>
        </article>

        <div className="stack">
          {sourceConfigs.length === 0 ? <div className="empty-state">No source configurations exist for this tenant yet.</div> : null}
          {sourceConfigs.map((sourceConfig) => {
            const latestRun = latestRunByPlugin.get(sourceConfig.plugin_name) ?? null;
            return (
              <article key={sourceConfig.id} className="content-card stack">
                <div className="content-card__header">
                  <div>
                    <h3>{sourceConfig.plugin_name}</h3>
                    <div className="meta-row">
                      <span>Config #{sourceConfig.id}</span>
                      <span>Last fetch {formatDate(sourceConfig.last_fetched_at)}</span>
                    </div>
                  </div>
                  <StatusBadge tone={sourceConfig.is_active ? "positive" : "neutral"}>
                    {sourceConfig.is_active ? "active" : "disabled"}
                  </StatusBadge>
                </div>

                <form className="stack" action={`/api/source-configs/${sourceConfig.id}`} method="POST">
                  <input type="hidden" name="tenantId" value={selectedTenant.id} />
                  <input type="hidden" name="redirectTo" value={`/admin/sources?tenant=${selectedTenant.id}`} />
                  <label className="field">
                    <span>Plugin</span>
                    <input name="plugin_name" defaultValue={sourceConfig.plugin_name} readOnly />
                  </label>
                  <label className="field">
                    <span>Config JSON</span>
                    <textarea name="config_json" defaultValue={JSON.stringify(sourceConfig.config, null, 2)} />
                  </label>
                  <label className="field">
                    <span>Active</span>
                    <select name="is_active" defaultValue={sourceConfig.is_active ? "true" : "false"}>
                      <option value="true">Active</option>
                      <option value="false">Disabled</option>
                    </select>
                  </label>
                  <div className="meta-row">
                    <span>Latest run: {latestRun ? latestRun.status : "none"}</span>
                    <span>{latestRun?.error_message || "No recent error"}</span>
                  </div>
                  <button className="button" type="submit">
                    Save source
                  </button>
                </form>
              </article>
            );
          })}
        </div>
      </section>
    </AppShell>
  );
}