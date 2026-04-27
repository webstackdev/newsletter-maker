import { NextResponse } from "next/server"

import { getContentSkillResults } from "@/lib/api"

export async function GET(request: Request) {
  const url = new URL(request.url)
  const projectId = Number.parseInt(url.searchParams.get("projectId") || "0", 10)
  const contentId = Number.parseInt(
    url.searchParams.get("contentId") || "0",
    10,
  )

  if (!projectId || !contentId) {
    return NextResponse.json(
      { error: "projectId and contentId are required." },
      { status: 400 },
    )
  }

  try {
    const skillResults = await getContentSkillResults(projectId, contentId)
    return NextResponse.json(skillResults)
  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : "Unable to load content skill results."

    return NextResponse.json({ error: message }, { status: 400 })
  }
}
