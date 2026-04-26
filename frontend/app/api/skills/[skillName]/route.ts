import { NextResponse } from "next/server";

import { runContentSkill } from "@/lib/api";
import type { ContentSkillName } from "@/lib/types";

function buildRedirectUrl(request: Request, redirectTo: string, params: Record<string, string>) {
  const url = new URL(redirectTo || "/", request.url);
  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, value);
  }
  return url;
}

export async function POST(request: Request, context: { params: Promise<{ skillName: string }> }) {
  const { skillName } = await context.params;
  const formData = await request.formData();
  const redirectTo = String(formData.get("redirectTo") || "/");

  try {
    const tenantId = Number.parseInt(String(formData.get("tenantId") || "0"), 10);
    const contentId = Number.parseInt(String(formData.get("contentId") || "0"), 10);
    const result = await runContentSkill(tenantId, contentId, skillName as ContentSkillName);
    if (result.status === "failed") {
      return NextResponse.redirect(
        buildRedirectUrl(request, redirectTo, {
          error: result.error_message || `${skillName} failed.`,
        }),
      );
    }
    return NextResponse.redirect(
      buildRedirectUrl(request, redirectTo, {
        message: `${skillName} completed.`,
      }),
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : `Unable to run ${skillName}.`;
    return NextResponse.redirect(buildRedirectUrl(request, redirectTo, { error: message }));
  }
}