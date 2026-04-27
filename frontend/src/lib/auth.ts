import type { NextAuthOptions, User } from "next-auth"
import NextAuth from "next-auth"
import CredentialsProvider from "next-auth/providers/credentials"
import GithubProvider from "next-auth/providers/github"
import GoogleProvider from "next-auth/providers/google"

type BackendAuthPayload = {
  access?: string
  detail?: string
  key?: string
  non_field_errors?: string[]
  refresh?: string
  user?: Record<string, unknown>
  [key: string]: unknown
}

type AuthenticatedUser = User & {
  backendAuth?: BackendAuthPayload
}

const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL

async function parseBackendResponse(response: Response) {
  const contentType = response.headers.get("content-type") ?? ""
  const text = await response.text()

  if (!text) {
    return null
  }

  if (contentType.includes("json")) {
    try {
      return JSON.parse(text) as BackendAuthPayload
    } catch {
      return null
    }
  }

  return null
}

async function postBackendAuth(
  path: string,
  body: Record<string, unknown>,
): Promise<BackendAuthPayload> {
  if (!apiBaseUrl) {
    throw new Error("NEXT_PUBLIC_API_URL is not configured.")
  }

  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })

  const payload = await parseBackendResponse(response)

  if (!response.ok) {
    const message =
      typeof payload?.detail === "string"
        ? payload.detail
        : typeof payload?.non_field_errors?.[0] === "string"
          ? payload.non_field_errors[0]
          : "Authentication failed."
    throw new Error(message)
  }

  return payload ?? {}
}

const providers = []

providers.push(
  CredentialsProvider({
    name: "Credentials",
    credentials: {
      username: { label: "Username or email", type: "text" },
      password: { label: "Password", type: "password" },
    },
    async authorize(credentials) {
      const username = credentials?.username?.trim()
      const password = credentials?.password

      if (!username || !password) {
        throw new Error("Enter both username and password.")
      }

      const backendAuth = await postBackendAuth("/api/auth/login/", {
        username,
        password,
      })

      return {
        id: username,
        name: username,
        backendAuth,
      } satisfies AuthenticatedUser
    },
  }),
)

if (process.env.GITHUB_ID && process.env.GITHUB_SECRET) {
  providers.push(
    GithubProvider({
      clientId: process.env.GITHUB_ID,
      clientSecret: process.env.GITHUB_SECRET,
    }),
  )
}

if (process.env.GOOGLE_ID && process.env.GOOGLE_SECRET) {
  providers.push(
    GoogleProvider({
      clientId: process.env.GOOGLE_ID,
      clientSecret: process.env.GOOGLE_SECRET,
    }),
  )
}

export const authOptions: NextAuthOptions = {
  providers,
  pages: {
    signIn: "/login",
  },
  session: {
    strategy: "jwt",
  },
  callbacks: {
    async signIn({ user, account }) {
      if (!account) {
        return false
      }

      if (account.provider === "credentials") {
        return true
      }

      try {
        if (typeof account.access_token !== "string") {
          return false
        }

        ;(user as AuthenticatedUser).backendAuth = await postBackendAuth(
          `/api/auth/${account.provider}/`,
          { access_token: account.access_token },
        )

        return true
      } catch {
        return false
      }
    },
    async jwt({ token, user }) {
      if (user && "backendAuth" in user) {
        token.backendAuth = (user as AuthenticatedUser).backendAuth
      }

      return token
    },
    async session({ session, token }) {
      const enrichedSession = session as typeof session & {
        backendAuth?: BackendAuthPayload
      }

      if (token.backendAuth) {
        enrichedSession.backendAuth = token.backendAuth as BackendAuthPayload
      }

      return enrichedSession
    },
  },
}

const handler = NextAuth(authOptions)

export default handler
export { handler }
