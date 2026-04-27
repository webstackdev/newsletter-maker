import { NextResponse } from "next/server"

import { runContentSkill } from "@/lib/api"
import type { ContentSkillName } from "@/lib/types"

function isAsyncSkillStatus(status: string) {
  return status === "pending" || status === "running"
}

function buildRedirectUrl(
  request: Request,
  redirectTo: string,
  params: Record<string, string>,
) {
  const url = new URL(redirectTo || "/", request.url)
  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, value)
  }
  return url
}

export async function POST(
  request: Request,
  context: { params: Promise<{ skillName: string }> },
) {
  const { skillName } = await context.params
  const responseMode = new URL(request.url).searchParams.get("mode")
  const formData = await request.formData()
  const redirectTo = String(formData.get("redirectTo") || "/")

  try {
    const projectId = Number.parseInt(
      String(formData.get("projectId") || "0"),
      10,
    )
    const contentId = Number.parseInt(
      String(formData.get("contentId") || "0"),
      10,
    )
    const result = await runContentSkill(
      projectId,
      contentId,
      skillName as ContentSkillName,
    )
    const message = isAsyncSkillStatus(result.status)
      ? `${skillName} queued.`
      : result.status === "failed"
        ? result.error_message || `${skillName} failed.`
        : `${skillName} completed.`

    if (responseMode === "json") {
      return NextResponse.json(
        {
          message,
          skillResult: result,
        },
        {
          status: isAsyncSkillStatus(result.status)
            ? 202
            : result.status === "failed"
              ? 400
              : 200,
        },
      )
    }

    if (result.status === "failed") {
      return NextResponse.redirect(
        buildRedirectUrl(request, redirectTo, {
          error: result.error_message || `${skillName} failed.`,
        }),
      )
    }
    return NextResponse.redirect(
      buildRedirectUrl(request, redirectTo, {
        message,
      }),
    )
  } catch (error) {
    const message =
      error instanceof Error ? error.message : `Unable to run ${skillName}.`

    if (responseMode === "json") {
      return NextResponse.json({ message }, { status: 400 })
    }

    return NextResponse.redirect(
      buildRedirectUrl(request, redirectTo, { error: message }),
    )
  }
}
