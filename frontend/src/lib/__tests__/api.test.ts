import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const { getServerSessionMock } = vi.hoisted(() => ({
  getServerSessionMock: vi.fn(),
}))

vi.mock("server-only", () => ({}))

vi.mock("@/lib/auth", () => ({
  authOptions: {},
}))

vi.mock("next-auth", () => ({
  getServerSession: getServerSessionMock,
}))

vi.mock("react", async () => {
  const actual = await vi.importActual<typeof import("react")>("react")

  return {
    ...actual,
    cache: <T extends (...args: never[]) => unknown>(fn: T) => fn,
  }
})

function jsonResponse(body: unknown, init?: ResponseInit) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    ...init,
  })
}

describe("api helpers", () => {
  beforeEach(() => {
    vi.resetModules()
    vi.unstubAllEnvs()
    vi.stubEnv("NEWSLETTER_API_BASE_URL", "https://api.example.com")
    vi.stubEnv("NEWSLETTER_API_USERNAME", "frontend-user")
    vi.stubEnv("NEWSLETTER_API_PASSWORD", "frontend-pass")
    getServerSessionMock.mockReset()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("prefers the backend token key for authenticated API requests", async () => {
    getServerSessionMock.mockResolvedValue({ backendAuth: { key: "abc123" } })
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }))
    vi.stubGlobal("fetch", fetchMock)

    const { apiFetch } = await import("@/lib/api")
    await apiFetch("/api/v1/projects/")

    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.com/api/v1/projects/",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Token abc123" }),
      }),
    )
  })

  it("falls back to basic auth when the session has no backend credentials", async () => {
    getServerSessionMock.mockResolvedValue(null)
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }))
    vi.stubGlobal("fetch", fetchMock)

    const { apiFetch } = await import("@/lib/api")
    await apiFetch("/api/v1/projects/")

    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.com/api/v1/projects/",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Basic ZnJvbnRlbmQtdXNlcjpmcm9udGVuZC1wYXNz",
        }),
      }),
    )
  })

  it("surfaces a normalized error preview for failed requests", async () => {
    getServerSessionMock.mockResolvedValue(null)
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response("bad    request\n\nbody", {
          status: 500,
          headers: { "Content-Type": "text/plain" },
        }),
      )
    vi.stubGlobal("fetch", fetchMock)

    const { apiFetch } = await import("@/lib/api")

    await expect(apiFetch("/api/v1/projects/")).rejects.toThrow(
      "API request failed (500) from https://api.example.com/api/v1/projects/ with text/plain: bad request body",
    )
  })

  it("filters content skill results for the requested content item", async () => {
    getServerSessionMock.mockResolvedValue({ backendAuth: { access: "jwt-token" } })
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse([
        { id: 1, content: 9, skill_name: "summarization" },
        { id: 2, content: 2, skill_name: "relevance_scoring" },
      ]),
    )
    vi.stubGlobal("fetch", fetchMock)

    const { getContentSkillResults } = await import("@/lib/api")
    const skillResults = await getContentSkillResults(4, 9)

    expect(skillResults).toEqual([{ id: 1, content: 9, skill_name: "summarization" }])
  })
})
