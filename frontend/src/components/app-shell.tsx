import Link from "next/link"
import type { ReactNode } from "react"

import type { Project } from "@/lib/types"

type AppShellProps = {
  title: string
  description: string
  projects: Project[]
  selectedProjectId: number | null
  children: ReactNode
}

export function AppShell({
  title,
  description,
  projects,
  selectedProjectId,
  children,
}: AppShellProps) {
  const projectQuery = selectedProjectId ? `?project=${selectedProjectId}` : ""

  return (
    <div className="min-h-screen md:grid md:grid-cols-[320px_minmax(0,1fr)]">
      <aside className="flex flex-col gap-8 bg-[rgba(20,31,28,0.94)] p-5 text-[#f7f0e7] md:p-8">
        <div>
          <p className="m-0 text-[0.78rem] uppercase tracking-[0.12em] opacity-70">
            Newsletter Maker
          </p>
          <h1 className="mt-1 font-[family:var(--font-display)] text-[clamp(2rem,5vw,2.8rem)] font-bold leading-[0.95]">
            Editor cockpit
          </h1>
          <p className="mt-4 text-sm leading-6 text-[rgba(247,240,231,0.74)]">
            A compact review surface for relevance-ranked content, review work,
            and source health.
          </p>
        </div>

        <nav className="grid gap-4">
          <Link
            className="rounded-[18px] border border-[rgba(247,240,231,0.08)] bg-white/3 px-4 py-4 transition hover:-translate-y-0.5 hover:border-[rgba(247,240,231,0.22)] hover:bg-white/6"
            href={`/${projectQuery}`}
          >
            Dashboard
          </Link>
          <Link
            className="rounded-[18px] border border-[rgba(247,240,231,0.08)] bg-white/3 px-4 py-4 transition hover:-translate-y-0.5 hover:border-[rgba(247,240,231,0.22)] hover:bg-white/6"
            href={`/entities${projectQuery}`}
          >
            Entities
          </Link>
          <Link
            className="rounded-[18px] border border-[rgba(247,240,231,0.08)] bg-white/3 px-4 py-4 transition hover:-translate-y-0.5 hover:border-[rgba(247,240,231,0.22)] hover:bg-white/6"
            href={`/admin/health${projectQuery}`}
          >
            Ingestion health
          </Link>
          <Link
            className="rounded-[18px] border border-[rgba(247,240,231,0.08)] bg-white/3 px-4 py-4 transition hover:-translate-y-0.5 hover:border-[rgba(247,240,231,0.22)] hover:bg-white/6"
            href={`/admin/sources${projectQuery}`}
          >
            Source configs
          </Link>
        </nav>

        <section>
          <p className="m-0 text-[0.78rem] uppercase tracking-[0.12em] opacity-70">
            Project
          </p>
          <div className="mt-4 grid gap-4">
            {projects.map((project) => {
              const isActive = project.id === selectedProjectId
              return (
                <Link
                  data-active={isActive ? "true" : "false"}
                  key={project.id}
                  href={`/?project=${project.id}`}
                  className={`grid gap-1 rounded-[18px] border px-4 py-4 transition hover:-translate-y-0.5 ${
                    isActive
                      ? "border-[rgba(240,205,131,0.46)] bg-[linear-gradient(180deg,rgba(194,122,44,0.18),rgba(255,255,255,0.03))]"
                      : "border-[rgba(247,240,231,0.08)] bg-white/3 hover:border-[rgba(247,240,231,0.22)] hover:bg-white/6"
                  }`}
                >
                  <span>{project.name}</span>
                  <small className="text-[rgba(247,240,231,0.64)]">
                    {project.topic_description}
                  </small>
                </Link>
              )
            })}
          </div>
        </section>
      </aside>

      <main className="p-5 md:p-8">
        <header className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between md:gap-6">
          <div>
            <p className="m-0 text-[0.78rem] uppercase tracking-[0.12em] opacity-70">
              Minimal dashboard
            </p>
            <h2 className="font-[family:var(--font-display)] text-[clamp(2rem,4vw,3.25rem)] font-bold">
              {title}
            </h2>
          </div>
          <p className="max-w-[36rem] text-sm leading-6 text-[#5d6d67] md:text-base">
            {description}
          </p>
        </header>
        {children}
      </main>
    </div>
  )
}
