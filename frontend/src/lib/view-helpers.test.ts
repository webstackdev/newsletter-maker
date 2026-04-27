import { describe, expect, it } from "vitest"

import type { Project } from "@/lib/types"
import {
  formatScore,
  getErrorMessage,
  getSearchParam,
  getSuccessMessage,
  healthTone,
  selectProject,
  truncateText,
} from "@/lib/view-helpers"

const projects: Project[] = [
  {
    id: 1,
    name: "AI Weekly",
    group: 3,
    topic_description: "Applied AI",
    content_retention_days: 30,
    created_at: "2026-04-27T00:00:00Z",
  },
  {
    id: 2,
    name: "Platform Weekly",
    group: 3,
    topic_description: "Platform engineering",
    content_retention_days: 30,
    created_at: "2026-04-27T00:00:00Z",
  },
]

describe("view helpers", () => {
  it("returns the first array value for a search param", () => {
    expect(getSearchParam({ project: ["2", "1"] }, "project")).toBe("2")
  })

  it("falls back to the first project when the query does not match", () => {
    expect(selectProject(projects, { project: "99" })).toEqual(projects[0])
  })

  it("returns null when no projects exist", () => {
    expect(selectProject([], { project: "1" })).toBeNull()
  })

  it("formats a score with two decimal places", () => {
    expect(formatScore(0.825)).toBe("0.82")
    expect(formatScore(null)).toBe("n/a")
  })

  it("truncates long text and keeps short text intact", () => {
    expect(truncateText("short text", 20)).toBe("short text")
    expect(truncateText("a".repeat(25), 20)).toBe(`${"a".repeat(20)}...`)
  })

  it("maps health states to badge tones", () => {
    expect(healthTone("healthy")).toBe("positive")
    expect(healthTone("degraded")).toBe("warning")
    expect(healthTone("failing")).toBe("negative")
    expect(healthTone("idle")).toBe("neutral")
  })

  it("reads error and success messages from search params", () => {
    expect(getErrorMessage({ error: "bad request" })).toBe("bad request")
    expect(getSuccessMessage({ message: "saved" })).toBe("saved")
  })
})
