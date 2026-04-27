import type { NextAuthOptions } from "next-auth"
import NextAuth from "next-auth"
import GithubProvider from "next-auth/providers/github"
import GoogleProvider from "next-auth/providers/google"

const providers = []

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
  callbacks: {
    async signIn({ account }) {
      // After social login succeeds on the frontend,
      // ping the Django API to sync the user and mint app tokens.
      if (!account?.provider || typeof account.access_token !== "string") {
        return false
      }

      if (!process.env.NEXT_PUBLIC_API_URL) {
        return false
      }

      try {
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL}/api/auth/${account.provider}/`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ access_token: account.access_token }),
          },
        )

        return response.ok
      } catch {
        return false
      }
    },
  },
}

const handler = NextAuth(authOptions)

export default handler
export { handler }
