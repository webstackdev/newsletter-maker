import type { ReactNode } from "react";

import Link from "next/link";

import type { Tenant } from "@/lib/types";

type AppShellProps = {
  title: string;
  description: string;
  tenants: Tenant[];
  selectedTenantId: number | null;
  children: ReactNode;
};

export function AppShell({ title, description, tenants, selectedTenantId, children }: AppShellProps) {
  const tenantQuery = selectedTenantId ? `?tenant=${selectedTenantId}` : "";

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="brand-lockup">
          <p className="eyebrow">Newsletter Maker</p>
          <h1>Editor cockpit</h1>
          <p className="sidebar-copy">
            A compact review surface for relevance-ranked content, review work, and source health.
          </p>
        </div>

        <nav className="sidebar-nav">
          <Link href={`/${tenantQuery}`}>Dashboard</Link>
          <Link href={`/entities${tenantQuery}`}>Entities</Link>
          <Link href={`/admin/health${tenantQuery}`}>Ingestion health</Link>
          <Link href={`/admin/sources${tenantQuery}`}>Source configs</Link>
        </nav>

        <section className="tenant-switcher">
          <p className="eyebrow">Tenant</p>
          <div className="tenant-list">
            {tenants.map((tenant) => {
              const isActive = tenant.id === selectedTenantId;
              return (
                <Link
                  key={tenant.id}
                  href={`/?tenant=${tenant.id}`}
                  className={isActive ? "tenant-link tenant-link--active" : "tenant-link"}
                >
                  <span>{tenant.name}</span>
                  <small>{tenant.topic_description}</small>
                </Link>
              );
            })}
          </div>
        </section>
      </aside>

      <main className="app-main">
        <header className="page-header">
          <div>
            <p className="eyebrow">Minimal dashboard</p>
            <h2>{title}</h2>
          </div>
          <p className="page-description">{description}</p>
        </header>
        {children}
      </main>
    </div>
  );
}