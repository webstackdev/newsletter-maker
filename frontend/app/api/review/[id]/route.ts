import { NextResponse } from "next/server"

import { updateReviewQueueItem } from "@/lib/api"

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
  context: { params: Promise<{ id: string }> },
) {
  const { id } = await context.params
  const formData = await request.formData()
  const redirectTo = String(formData.get("redirectTo") || "/")

  try {
    const tenantId = Number.parseInt(
      String(formData.get("tenantId") || "0"),
      10,
    )
    const reviewId = Number.parseInt(id, 10)
    const resolved = String(formData.get("resolved") || "false") === "true"
    const resolution = String(formData.get("resolution") || "")
    await updateReviewQueueItem(reviewId, tenantId, { resolved, resolution })
    return NextResponse.redirect(
      buildRedirectUrl(request, redirectTo, {
        message: "Review item updated.",
      }),
    )
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Unable to update review item."
    return NextResponse.redirect(
      buildRedirectUrl(request, redirectTo, { error: message }),
    )
  }
}
