import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { AppShell } from "@/components/app-shell"
import type { Tenant } from "@/lib/types"

const tenants: Tenant[] = [
  {
    id: 1,
    name: "AI Weekly",
    user: 7,
    topic_description: "Applied AI",
    content_retention_days: 30,
    created_at: "2026-04-27T00:00:00Z",
  },
  {
    id: 2,
    name: "Platform Weekly",
    user: 7,
    topic_description: "Platform engineering",
    content_retention_days: 30,
    created_at: "2026-04-27T00:00:00Z",
  },
]

describe("AppShell", () => {
  it("renders the page title, description, and child content", () => {
    render(
      <AppShell
        title="Dashboard"
        description="A test description"
        tenants={tenants}
        selectedTenantId={1}
      >
        <div>Child content</div>
      </AppShell>,
    )

    expect(screen.getByRole("heading", { name: "Editor cockpit" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument()
    expect(screen.getByText("A test description")).toBeInTheDocument()
    expect(screen.getByText("Child content")).toBeInTheDocument()
  })

  it("adds the selected tenant query string to navigation links", () => {
    render(
      <AppShell
        title="Dashboard"
        description="A test description"
        tenants={tenants}
        selectedTenantId={2}
      >
        <div>Child content</div>
      </AppShell>,
    )

    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/?tenant=2")
    expect(screen.getByRole("link", { name: "Entities" })).toHaveAttribute("href", "/entities?tenant=2")
    expect(screen.getByRole("link", { name: "Ingestion health" })).toHaveAttribute(
      "href",
      "/admin/health?tenant=2",
    )
    expect(screen.getByRole("link", { name: "Source configs" })).toHaveAttribute(
      "href",
      "/admin/sources?tenant=2",
    )
  })

  it("marks the active tenant in the switcher", () => {
    render(
      <AppShell
        title="Dashboard"
        description="A test description"
        tenants={tenants}
        selectedTenantId={2}
      >
        <div>Child content</div>
      </AppShell>,
    )

    const activeTenant = screen.getByRole("link", { name: /Platform Weekly/i })
    const inactiveTenant = screen.getByRole("link", { name: /AI Weekly/i })

    expect(activeTenant).toHaveClass("tenant-link--active")
    expect(inactiveTenant).toHaveClass("tenant-link")
    expect(inactiveTenant).not.toHaveClass("tenant-link--active")
  })
})
