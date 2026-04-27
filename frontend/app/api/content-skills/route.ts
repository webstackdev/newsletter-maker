import { NextResponse } from "next/server"

import { getContentSkillResults } from "@/lib/api"

export async function GET(request: Request) {
  const url = new URL(request.url)
  const tenantId = Number.parseInt(url.searchParams.get("tenantId") || "0", 10)
  const contentId = Number.parseInt(
    url.searchParams.get("contentId") || "0",
    10,
  )

  if (!tenantId || !contentId) {
    return NextResponse.json(
      { error: "tenantId and contentId are required." },
      { status: 400 },
    )
  }

  try {
    const skillResults = await getContentSkillResults(tenantId, contentId)
    return NextResponse.json(skillResults)
  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : "Unable to load content skill results."

    return NextResponse.json({ error: message }, { status: 400 })
  }
}