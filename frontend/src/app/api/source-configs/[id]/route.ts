import { NextResponse } from "next/server"

import { updateSourceConfig } from "@/lib/api"

function buildRedirectUrl(
  request: Request,
  redirectTo: string,
  params: Record<string, string>,
) {
  const url = new URL(redirectTo || "/admin/sources", request.url)
  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, value)
  }
  return url
}

function parseConfigJson(rawValue: FormDataEntryValue | null) {
  const value = String(rawValue || "{}").trim()
  return JSON.parse(value) as Record<string, unknown>
}

export async function POST(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  const { id } = await context.params
  const formData = await request.formData()
  const redirectTo = String(formData.get("redirectTo") || "/admin/sources")

  try {
    const projectId = Number.parseInt(
      String(formData.get("projectId") || "0"),
      10,
    )
    const sourceConfigId = Number.parseInt(id, 10)
    await updateSourceConfig(sourceConfigId, projectId, {
      is_active: String(formData.get("is_active") || "true") === "true",
      config: parseConfigJson(formData.get("config_json")),
    })
    return NextResponse.redirect(
      buildRedirectUrl(request, redirectTo, { message: "Source updated." }),
    )
  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : "Unable to update source configuration."
    return NextResponse.redirect(
      buildRedirectUrl(request, redirectTo, { error: message }),
    )
  }
}
