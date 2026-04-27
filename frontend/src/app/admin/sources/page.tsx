import { AppShell } from "@/components/app-shell"
import { StatusBadge } from "@/components/status-badge"
import {
  getProjectIngestionRuns,
  getProjects,
  getProjectSourceConfigs,
} from "@/lib/api"
import {
  formatDate,
  getErrorMessage,
  getSuccessMessage,
  selectProject,
} from "@/lib/view-helpers"

type SourcesPageProps = {
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

export default async function SourcesPage({ searchParams }: SourcesPageProps) {
  const resolvedSearchParams = await searchParams
  const projects = await getProjects()
  const selectedProject = selectProject(projects, resolvedSearchParams)

  if (!selectedProject) {
    return (
      <AppShell
        title="Sources"
        description="No project found for this API user."
        projects={[]}
        selectedProjectId={null}
      >
        <div className={emptyStateClass}>
          Create a project first in Django admin.
        </div>
      </AppShell>
    )
  }

  const [sourceConfigs, ingestionRuns] = await Promise.all([
    getProjectSourceConfigs(selectedProject.id),
    getProjectIngestionRuns(selectedProject.id),
  ])
  const latestRunByPlugin = new Map<string, (typeof ingestionRuns)[number]>()
  for (const ingestionRun of ingestionRuns) {
    if (!latestRunByPlugin.has(ingestionRun.plugin_name)) {
      latestRunByPlugin.set(ingestionRun.plugin_name, ingestionRun)
    }
  }

  const errorMessage = getErrorMessage(resolvedSearchParams)
  const successMessage = getSuccessMessage(resolvedSearchParams)

  return (
    <AppShell
      title="Source configuration"
      description="Add, tune, and disable RSS feeds or Reddit subscriptions without leaving the editor dashboard."
      projects={projects}
      selectedProjectId={selectedProject.id}
    >
      {errorMessage ? (
        <div className={errorBannerClass}>{errorMessage}</div>
      ) : null}
      {successMessage ? (
        <div className={emptyStateClass}>{successMessage}</div>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.65fr)_minmax(280px,0.95fr)]">
        <article className={`${panelClass} space-y-4`}>
          <p className={eyebrowClass}>Add source</p>
          <form
            className="space-y-4"
            action="/api/source-configs"
            method="POST"
          >
            <input type="hidden" name="projectId" value={selectedProject.id} />
            <input
              type="hidden"
              name="redirectTo"
              value={`/admin/sources?project=${selectedProject.id}`}
            />
            <label className={labelClass}>
              <span className={labelTextClass}>Plugin</span>
              <select
                className={inputClass}
                name="plugin_name"
                defaultValue="rss"
              >
                <option value="rss">RSS</option>
                <option value="reddit">Reddit</option>
              </select>
            </label>
            <label className={labelClass}>
              <span className={labelTextClass}>Config JSON</span>
              <textarea
                className={`${inputClass} min-h-[120px] resize-y font-mono text-sm`}
                name="config_json"
                defaultValue={JSON.stringify(
                  { feed_url: "https://example.com/feed.xml" },
                  null,
                  2,
                )}
              />
            </label>
            <label className={labelClass}>
              <span className={labelTextClass}>Active</span>
              <select
                className={inputClass}
                name="is_active"
                defaultValue="true"
              >
                <option value="true">Active</option>
                <option value="false">Disabled</option>
              </select>
            </label>
            <button className={primaryButtonClass} type="submit">
              Create source
            </button>
          </form>
        </article>

        <div className="space-y-4">
          {sourceConfigs.length === 0 ? (
            <div className={emptyStateClass}>
              No source configurations exist for this project yet.
            </div>
          ) : null}
          {sourceConfigs.map((sourceConfig) => {
            const latestRun =
              latestRunByPlugin.get(sourceConfig.plugin_name) ?? null
            return (
              <article
                key={sourceConfig.id}
                className={`${panelClass} space-y-4`}
              >
                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                  <div>
                    <h3 className="font-[family:var(--font-display)] text-[1.45rem] font-bold">
                      {sourceConfig.plugin_name}
                    </h3>
                    <div className={metaRowClass}>
                      <span>Config #{sourceConfig.id}</span>
                      <span>
                        Last fetch {formatDate(sourceConfig.last_fetched_at)}
                      </span>
                    </div>
                  </div>
                  <StatusBadge
                    tone={sourceConfig.is_active ? "positive" : "neutral"}
                  >
                    {sourceConfig.is_active ? "active" : "disabled"}
                  </StatusBadge>
                </div>

                <form
                  className="space-y-4"
                  action={`/api/source-configs/${sourceConfig.id}`}
                  method="POST"
                >
                  <input
                    type="hidden"
                    name="projectId"
                    value={selectedProject.id}
                  />
                  <input
                    type="hidden"
                    name="redirectTo"
                    value={`/admin/sources?project=${selectedProject.id}`}
                  />
                  <label className={labelClass}>
                    <span className={labelTextClass}>Plugin</span>
                    <input
                      className={inputClass}
                      name="plugin_name"
                      defaultValue={sourceConfig.plugin_name}
                      readOnly
                    />
                  </label>
                  <label className={labelClass}>
                    <span className={labelTextClass}>Config JSON</span>
                    <textarea
                      className={`${inputClass} min-h-[120px] resize-y font-mono text-sm`}
                      name="config_json"
                      defaultValue={JSON.stringify(
                        sourceConfig.config,
                        null,
                        2,
                      )}
                    />
                  </label>
                  <label className={labelClass}>
                    <span className={labelTextClass}>Active</span>
                    <select
                      className={inputClass}
                      name="is_active"
                      defaultValue={sourceConfig.is_active ? "true" : "false"}
                    >
                      <option value="true">Active</option>
                      <option value="false">Disabled</option>
                    </select>
                  </label>
                  <div className={metaRowClass}>
                    <span>
                      Latest run: {latestRun ? latestRun.status : "none"}
                    </span>
                    <span>{latestRun?.error_message || "No recent error"}</span>
                  </div>
                  <button className={primaryButtonClass} type="submit">
                    Save source
                  </button>
                </form>
              </article>
            )
          })}
        </div>
      </section>
    </AppShell>
  )
}
