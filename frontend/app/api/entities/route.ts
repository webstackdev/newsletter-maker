import { NextResponse } from "next/server";

import { createEntity } from "@/lib/api";

function buildRedirectUrl(request: Request, redirectTo: string, params: Record<string, string>) {
  const url = new URL(redirectTo || "/entities", request.url);
  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, value);
  }
  return url;
}

export async function POST(request: Request) {
  const formData = await request.formData();
  const redirectTo = String(formData.get("redirectTo") || "/entities");

  try {
    const tenantId = Number.parseInt(String(formData.get("tenantId") || "0"), 10);
    await createEntity(tenantId, {
      name: String(formData.get("name") || ""),
      type: String(formData.get("type") || "vendor"),
      description: String(formData.get("description") || ""),
      website_url: String(formData.get("website_url") || ""),
      github_url: String(formData.get("github_url") || ""),
      linkedin_url: String(formData.get("linkedin_url") || ""),
      bluesky_handle: String(formData.get("bluesky_handle") || ""),
      mastodon_handle: String(formData.get("mastodon_handle") || ""),
      twitter_handle: String(formData.get("twitter_handle") || ""),
    });
    return NextResponse.redirect(buildRedirectUrl(request, redirectTo, { message: "Entity created." }));
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to create entity.";
    return NextResponse.redirect(buildRedirectUrl(request, redirectTo, { error: message }));
  }
}