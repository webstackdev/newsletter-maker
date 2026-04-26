import { NextResponse } from "next/server";

import { createFeedback } from "@/lib/api";

function buildRedirectUrl(request: Request, redirectTo: string, params: Record<string, string>) {
  const url = new URL(redirectTo || "/", request.url);
  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, value);
  }
  return url;
}

export async function POST(request: Request) {
  const formData = await request.formData();
  const redirectTo = String(formData.get("redirectTo") || "/");

  try {
    const tenantId = Number.parseInt(String(formData.get("tenantId") || "0"), 10);
    const contentId = Number.parseInt(String(formData.get("contentId") || "0"), 10);
    const feedbackType = String(formData.get("feedbackType") || "upvote") as "upvote" | "downvote";
    await createFeedback(tenantId, contentId, feedbackType);
    return NextResponse.redirect(buildRedirectUrl(request, redirectTo, { message: "Feedback saved." }));
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to save feedback.";
    return NextResponse.redirect(buildRedirectUrl(request, redirectTo, { error: message }));
  }
}