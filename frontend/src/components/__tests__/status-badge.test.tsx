import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { StatusBadge } from "@/components/status-badge"

describe("StatusBadge", () => {
  it("renders its children and tone class", () => {
    render(<StatusBadge tone="warning">Needs review</StatusBadge>)

    const badge = screen.getByText("Needs review")
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveAttribute("data-tone", "warning")
  })
})
