import { AppShell } from "@/components/app-shell"
import { StatusBadge } from "@/components/status-badge"
import { getTenantEntities, getTenants } from "@/lib/api"
import {
  formatDate,
  getErrorMessage,
  getSuccessMessage,
  selectTenant,
} from "@/lib/view-helpers"

type EntitiesPageProps = {
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
const inputClass =
  "w-full rounded-2xl border border-[#1f2b27]/12 bg-white/70 px-4 py-3 text-[#1f2b27] outline-none transition focus:border-[#156f68]/40 focus:ring-2 focus:ring-[#156f68]/15"
const labelClass = "grid gap-2"
const labelTextClass = "text-sm font-medium text-[#1f2b27]"
const primaryButtonClass =
  "inline-flex min-h-11 items-center justify-center rounded-full bg-[linear-gradient(135deg,#156f68,#1d8d83)] px-4 py-3 text-sm font-medium text-white transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
const dangerButtonClass =
  "inline-flex min-h-11 items-center justify-center rounded-full bg-[linear-gradient(135deg,#c55f4d,#da7a67)] px-4 py-3 text-sm font-medium text-white transition hover:brightness-105"

export default async function EntitiesPage({
  searchParams,
}: EntitiesPageProps) {
  const resolvedSearchParams = await searchParams
  const tenants = await getTenants()
  const selectedTenant = selectTenant(tenants, resolvedSearchParams)

  if (!selectedTenant) {
    return (
      <AppShell
        title="Entities"
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

  const entities = await getTenantEntities(selectedTenant.id)
  const errorMessage = getErrorMessage(resolvedSearchParams)
  const successMessage = getSuccessMessage(resolvedSearchParams)

  return (
    <AppShell
      title="Entity management"
      description="Create, update, and remove the people and organizations that anchor relevance for this tenant."
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
        <article className={`${panelClass} space-y-4`}>
          <p className={eyebrowClass}>Create entity</p>
          <form className="space-y-4" action="/api/entities" method="POST">
            <input type="hidden" name="tenantId" value={selectedTenant.id} />
            <input
              type="hidden"
              name="redirectTo"
              value={`/entities?tenant=${selectedTenant.id}`}
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <label className={labelClass}>
                <span className={labelTextClass}>Name</span>
                <input className={inputClass} name="name" required />
              </label>
              <label className={labelClass}>
                <span className={labelTextClass}>Type</span>
                <select
                  className={inputClass}
                  name="type"
                  defaultValue="vendor"
                >
                  <option value="individual">Individual</option>
                  <option value="vendor">Vendor</option>
                  <option value="organization">Organization</option>
                </select>
              </label>
            </div>
            <label className={labelClass}>
              <span className={labelTextClass}>Description</span>
              <textarea
                className={`${inputClass} min-h-[120px] resize-y`}
                name="description"
              />
            </label>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className={labelClass}>
                <span className={labelTextClass}>Website URL</span>
                <input className={inputClass} name="website_url" type="url" />
              </label>
              <label className={labelClass}>
                <span className={labelTextClass}>GitHub URL</span>
                <input className={inputClass} name="github_url" type="url" />
              </label>
              <label className={labelClass}>
                <span className={labelTextClass}>LinkedIn URL</span>
                <input className={inputClass} name="linkedin_url" type="url" />
              </label>
              <label className={labelClass}>
                <span className={labelTextClass}>Bluesky handle</span>
                <input className={inputClass} name="bluesky_handle" />
              </label>
              <label className={labelClass}>
                <span className={labelTextClass}>Mastodon handle</span>
                <input className={inputClass} name="mastodon_handle" />
              </label>
              <label className={labelClass}>
                <span className={labelTextClass}>Twitter handle</span>
                <input className={inputClass} name="twitter_handle" />
              </label>
            </div>
            <button className={primaryButtonClass} type="submit">
              Create entity
            </button>
          </form>
        </article>

        <div className="space-y-4">
          {entities.length === 0 ? (
            <div className={emptyStateClass}>
              No entities exist for this tenant yet.
            </div>
          ) : null}
          {entities.map((entity) => (
            <article key={entity.id} className={`${panelClass} space-y-4`}>
              <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div>
                  <h3 className="font-[family:var(--font-display)] text-[1.45rem] font-bold">
                    {entity.name}
                  </h3>
                  <div className={metaRowClass}>
                    <span>{formatDate(entity.created_at)}</span>
                    <span>Authority {entity.authority_score.toFixed(2)}</span>
                  </div>
                </div>
                <StatusBadge tone="neutral">{entity.type}</StatusBadge>
              </div>
              <form
                className="space-y-4"
                action={`/api/entities/${entity.id}`}
                method="POST"
              >
                <input
                  type="hidden"
                  name="tenantId"
                  value={selectedTenant.id}
                />
                <input
                  type="hidden"
                  name="redirectTo"
                  value={`/entities?tenant=${selectedTenant.id}`}
                />
                <input type="hidden" name="intent" value="update" />
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className={labelClass}>
                    <span className={labelTextClass}>Name</span>
                    <input
                      className={inputClass}
                      name="name"
                      defaultValue={entity.name}
                      required
                    />
                  </label>
                  <label className={labelClass}>
                    <span className={labelTextClass}>Type</span>
                    <select
                      className={inputClass}
                      name="type"
                      defaultValue={entity.type}
                    >
                      <option value="individual">Individual</option>
                      <option value="vendor">Vendor</option>
                      <option value="organization">Organization</option>
                    </select>
                  </label>
                </div>
                <label className={labelClass}>
                  <span className={labelTextClass}>Description</span>
                  <textarea
                    className={`${inputClass} min-h-[120px] resize-y`}
                    name="description"
                    defaultValue={entity.description}
                  />
                </label>
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className={labelClass}>
                    <span className={labelTextClass}>Website URL</span>
                    <input
                      className={inputClass}
                      name="website_url"
                      type="url"
                      defaultValue={entity.website_url}
                    />
                  </label>
                  <label className={labelClass}>
                    <span className={labelTextClass}>GitHub URL</span>
                    <input
                      className={inputClass}
                      name="github_url"
                      type="url"
                      defaultValue={entity.github_url}
                    />
                  </label>
                  <label className={labelClass}>
                    <span className={labelTextClass}>LinkedIn URL</span>
                    <input
                      className={inputClass}
                      name="linkedin_url"
                      type="url"
                      defaultValue={entity.linkedin_url}
                    />
                  </label>
                  <label className={labelClass}>
                    <span className={labelTextClass}>Bluesky handle</span>
                    <input
                      className={inputClass}
                      name="bluesky_handle"
                      defaultValue={entity.bluesky_handle}
                    />
                  </label>
                  <label className={labelClass}>
                    <span className={labelTextClass}>Mastodon handle</span>
                    <input
                      className={inputClass}
                      name="mastodon_handle"
                      defaultValue={entity.mastodon_handle}
                    />
                  </label>
                  <label className={labelClass}>
                    <span className={labelTextClass}>Twitter handle</span>
                    <input
                      className={inputClass}
                      name="twitter_handle"
                      defaultValue={entity.twitter_handle}
                    />
                  </label>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <button className={primaryButtonClass} type="submit">
                    Save changes
                  </button>
                </div>
              </form>
              <form action={`/api/entities/${entity.id}`} method="POST">
                <input
                  type="hidden"
                  name="tenantId"
                  value={selectedTenant.id}
                />
                <input
                  type="hidden"
                  name="redirectTo"
                  value={`/entities?tenant=${selectedTenant.id}`}
                />
                <input type="hidden" name="intent" value="delete" />
                <button className={dangerButtonClass} type="submit">
                  Delete entity
                </button>
              </form>
            </article>
          ))}
        </div>
      </section>
    </AppShell>
  )
}
