import { beforeEach, describe, expect, it, vi } from "vitest"

const {
  credentialsProviderMock,
  githubProviderMock,
  googleProviderMock,
  nextAuthMock,
} = vi.hoisted(() => ({
  credentialsProviderMock: vi.fn((config: Record<string, unknown>) => ({
    id: "credentials",
    ...config,
  })),
  githubProviderMock: vi.fn((config: Record<string, unknown>) => ({
    id: "github",
    ...config,
  })),
  googleProviderMock: vi.fn((config: Record<string, unknown>) => ({
    id: "google",
    ...config,
  })),
  nextAuthMock: vi.fn(() => "next-auth-handler"),
}))

vi.mock("next-auth", () => ({
  default: nextAuthMock,
}))

vi.mock("next-auth/providers/credentials", () => ({
  default: credentialsProviderMock,
}))

vi.mock("next-auth/providers/github", () => ({
  default: githubProviderMock,
}))

vi.mock("next-auth/providers/google", () => ({
  default: googleProviderMock,
}))

function jsonResponse(body: unknown, init?: ResponseInit) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    ...init,
  })
}

describe("authOptions", () => {
  beforeEach(() => {
    vi.resetModules()
    vi.unstubAllEnvs()
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.com")
    credentialsProviderMock.mockClear()
    githubProviderMock.mockClear()
    googleProviderMock.mockClear()
    nextAuthMock.mockClear()
  })

  it("authorizes credentials against the backend auth endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ key: "abc123", access: "jwt" }),
    )
    vi.stubGlobal("fetch", fetchMock)

    const { authOptions } = await import("@/lib/auth")
    const credentialsProvider = authOptions.providers.find(
      (provider) => provider.id === "credentials",
    ) as { authorize: (credentials: Record<string, string>) => Promise<unknown> }

    const user = await credentialsProvider.authorize({
      username: "  alice@example.com ",
      password: "secret",
    })

    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.com/api/auth/login/",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          username: "alice@example.com",
          password: "secret",
        }),
      }),
    )
    expect(user).toEqual({
      id: "alice@example.com",
      name: "alice@example.com",
      backendAuth: { key: "abc123", access: "jwt" },
    })
  })

  it("rejects missing credentials before calling the backend", async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal("fetch", fetchMock)

    const { authOptions } = await import("@/lib/auth")
    const credentialsProvider = authOptions.providers.find(
      (provider) => provider.id === "credentials",
    ) as { authorize: (credentials: Record<string, string>) => Promise<unknown> }

    await expect(
      credentialsProvider.authorize({ username: "", password: "" }),
    ).rejects.toThrow("Enter both username and password.")
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("enriches social sign-in users with backend auth when access tokens are present", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ key: "social-key" }))
    vi.stubGlobal("fetch", fetchMock)

    const { authOptions } = await import("@/lib/auth")
    const user: Record<string, unknown> = { id: "1" }

    const result = await authOptions.callbacks?.signIn?.({
      user: user as never,
      account: { provider: "github", access_token: "provider-token" } as never,
      profile: undefined,
      email: undefined,
      credentials: undefined,
    })

    expect(result).toBe(true)
    expect(user.backendAuth).toEqual({ key: "social-key" })
  })

  it("copies backendAuth through jwt and session callbacks", async () => {
    const { authOptions } = await import("@/lib/auth")

    const token = await authOptions.callbacks?.jwt?.({
      token: {},
      user: { backendAuth: { key: "persisted-key" } } as never,
      account: null,
      profile: undefined,
      trigger: "signIn",
      isNewUser: false,
      session: undefined,
    })

    const session = await authOptions.callbacks?.session?.({
      session: { user: {} } as never,
      token: token as never,
      user: undefined,
      newSession: undefined,
      trigger: undefined,
    })

    expect(token).toEqual({ backendAuth: { key: "persisted-key" } })
    expect(session).toMatchObject({ backendAuth: { key: "persisted-key" } })
  })
})
