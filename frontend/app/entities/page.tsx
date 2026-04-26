import { AppShell } from "@/components/app-shell";
import { StatusBadge } from "@/components/status-badge";
import { getTenantEntities, getTenants } from "@/lib/api";
import { formatDate, getErrorMessage, getSuccessMessage, selectTenant } from "@/lib/view-helpers";

type EntitiesPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function EntitiesPage({ searchParams }: EntitiesPageProps) {
  const resolvedSearchParams = await searchParams;
  const tenants = await getTenants();
  const selectedTenant = selectTenant(tenants, resolvedSearchParams);

  if (!selectedTenant) {
    return (
      <AppShell title="Entities" description="No tenant found for this API user." tenants={[]} selectedTenantId={null}>
        <div className="empty-state">Create a tenant first in Django admin.</div>
      </AppShell>
    );
  }

  const entities = await getTenantEntities(selectedTenant.id);
  const errorMessage = getErrorMessage(resolvedSearchParams);
  const successMessage = getSuccessMessage(resolvedSearchParams);

  return (
    <AppShell
      title="Entity management"
      description="Create, update, and remove the people and organizations that anchor relevance for this tenant."
      tenants={tenants}
      selectedTenantId={selectedTenant.id}
    >
      {errorMessage ? <div className="error-banner">{errorMessage}</div> : null}
      {successMessage ? <div className="empty-state">{successMessage}</div> : null}

      <section className="content-grid">
        <article className="form-card stack">
          <p className="eyebrow">Create entity</p>
          <form className="stack" action="/api/entities" method="POST">
            <input type="hidden" name="tenantId" value={selectedTenant.id} />
            <input type="hidden" name="redirectTo" value={`/entities?tenant=${selectedTenant.id}`} />
            <div className="field-grid">
              <label className="field">
                <span>Name</span>
                <input name="name" required />
              </label>
              <label className="field">
                <span>Type</span>
                <select name="type" defaultValue="vendor">
                  <option value="individual">Individual</option>
                  <option value="vendor">Vendor</option>
                  <option value="organization">Organization</option>
                </select>
              </label>
            </div>
            <label className="field">
              <span>Description</span>
              <textarea name="description" />
            </label>
            <div className="field-grid">
              <label className="field">
                <span>Website URL</span>
                <input name="website_url" type="url" />
              </label>
              <label className="field">
                <span>GitHub URL</span>
                <input name="github_url" type="url" />
              </label>
              <label className="field">
                <span>LinkedIn URL</span>
                <input name="linkedin_url" type="url" />
              </label>
              <label className="field">
                <span>Bluesky handle</span>
                <input name="bluesky_handle" />
              </label>
              <label className="field">
                <span>Mastodon handle</span>
                <input name="mastodon_handle" />
              </label>
              <label className="field">
                <span>Twitter handle</span>
                <input name="twitter_handle" />
              </label>
            </div>
            <button className="button" type="submit">
              Create entity
            </button>
          </form>
        </article>

        <div className="stack">
          {entities.length === 0 ? <div className="empty-state">No entities exist for this tenant yet.</div> : null}
          {entities.map((entity) => (
            <article key={entity.id} className="content-card stack">
              <div className="content-card__header">
                <div>
                  <h3>{entity.name}</h3>
                  <div className="meta-row">
                    <span>{formatDate(entity.created_at)}</span>
                    <span>Authority {entity.authority_score.toFixed(2)}</span>
                  </div>
                </div>
                <StatusBadge tone="neutral">{entity.type}</StatusBadge>
              </div>
              <form className="stack" action={`/api/entities/${entity.id}`} method="POST">
                <input type="hidden" name="tenantId" value={selectedTenant.id} />
                <input type="hidden" name="redirectTo" value={`/entities?tenant=${selectedTenant.id}`} />
                <input type="hidden" name="intent" value="update" />
                <div className="field-grid">
                  <label className="field">
                    <span>Name</span>
                    <input name="name" defaultValue={entity.name} required />
                  </label>
                  <label className="field">
                    <span>Type</span>
                    <select name="type" defaultValue={entity.type}>
                      <option value="individual">Individual</option>
                      <option value="vendor">Vendor</option>
                      <option value="organization">Organization</option>
                    </select>
                  </label>
                </div>
                <label className="field">
                  <span>Description</span>
                  <textarea name="description" defaultValue={entity.description} />
                </label>
                <div className="field-grid">
                  <label className="field">
                    <span>Website URL</span>
                    <input name="website_url" type="url" defaultValue={entity.website_url} />
                  </label>
                  <label className="field">
                    <span>GitHub URL</span>
                    <input name="github_url" type="url" defaultValue={entity.github_url} />
                  </label>
                  <label className="field">
                    <span>LinkedIn URL</span>
                    <input name="linkedin_url" type="url" defaultValue={entity.linkedin_url} />
                  </label>
                  <label className="field">
                    <span>Bluesky handle</span>
                    <input name="bluesky_handle" defaultValue={entity.bluesky_handle} />
                  </label>
                  <label className="field">
                    <span>Mastodon handle</span>
                    <input name="mastodon_handle" defaultValue={entity.mastodon_handle} />
                  </label>
                  <label className="field">
                    <span>Twitter handle</span>
                    <input name="twitter_handle" defaultValue={entity.twitter_handle} />
                  </label>
                </div>
                <div className="action-row">
                  <button className="button" type="submit">
                    Save changes
                  </button>
                </div>
              </form>
              <form action={`/api/entities/${entity.id}`} method="POST">
                <input type="hidden" name="tenantId" value={selectedTenant.id} />
                <input type="hidden" name="redirectTo" value={`/entities?tenant=${selectedTenant.id}`} />
                <input type="hidden" name="intent" value="delete" />
                <button className="danger-button button" type="submit">
                  Delete entity
                </button>
              </form>
            </article>
          ))}
        </div>
      </section>
    </AppShell>
  );
}