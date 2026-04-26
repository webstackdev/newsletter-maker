import { NextResponse } from "next/server";

import { deleteEntity, updateEntity } from "@/lib/api";

function buildRedirectUrl(request: Request, redirectTo: string, params: Record<string, string>) {
  const url = new URL(redirectTo || "/entities", request.url);
  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, value);
  }
  return url;
}

export async function POST(request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const formData = await request.formData();
  const redirectTo = String(formData.get("redirectTo") || "/entities");

  try {
    const tenantId = Number.parseInt(String(formData.get("tenantId") || "0"), 10);
    const entityId = Number.parseInt(id, 10);
    const intent = String(formData.get("intent") || "update");

    if (intent === "delete") {
      await deleteEntity(entityId, tenantId);
      return NextResponse.redirect(buildRedirectUrl(request, redirectTo, { message: "Entity deleted." }));
    }

    await updateEntity(entityId, tenantId, {
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
    return NextResponse.redirect(buildRedirectUrl(request, redirectTo, { message: "Entity updated." }));
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to save entity.";
    return NextResponse.redirect(buildRedirectUrl(request, redirectTo, { error: message }));
  }
}