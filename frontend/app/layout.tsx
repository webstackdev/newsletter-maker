import "./globals.css"

import type { Metadata } from "next"
import { Fraunces, Space_Grotesk } from "next/font/google"
import type { ReactNode } from "react"

import { QueryProvider } from "@/components/query-provider"

const display = Fraunces({
  variable: "--font-display",
  subsets: ["latin"],
})

const body = Space_Grotesk({
  variable: "--font-body",
  subsets: ["latin"],
})

export const metadata: Metadata = {
  title: "Newsletter Maker Frontend",
  description: "Minimal dashboard for reviewing ingested newsletter content.",
}

export default function RootLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body
        className={`${display.variable} ${body.variable} min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(21,111,104,0.14),transparent_38%),radial-gradient(circle_at_top_right,rgba(194,122,44,0.14),transparent_28%),linear-gradient(180deg,#f6f1e9_0%,#efe6da_100%)] font-[family:var(--font-body),sans-serif] text-[#1f2b27] antialiased`}
      >
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  )
}
