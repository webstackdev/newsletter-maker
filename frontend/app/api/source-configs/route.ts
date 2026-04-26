import { NextResponse } from "next/server";

import { createSourceConfig } from "@/lib/api";

function buildRedirectUrl(request: Request, redirectTo: string, params: Record<string, string>) {
  const url = new URL(redirectTo || "/admin/sources", request.url);
  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, value);
  }
  return url;
}

function parseConfigJson(rawValue: FormDataEntryValue | null) {
  const value = String(rawValue || "{}").trim();
  return JSON.parse(value) as Record<string, unknown>;
}

export async function POST(request: Request) {
  const formData = await request.formData();
  const redirectTo = String(formData.get("redirectTo") || "/admin/sources");

  try {
    const tenantId = Number.parseInt(String(formData.get("tenantId") || "0"), 10);
    await createSourceConfig(tenantId, {
      plugin_name: String(formData.get("plugin_name") || "rss"),
      config: parseConfigJson(formData.get("config_json")),
      is_active: String(formData.get("is_active") || "true") === "true",
    });
    return NextResponse.redirect(buildRedirectUrl(request, redirectTo, { message: "Source created." }));
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to create source configuration.";
    return NextResponse.redirect(buildRedirectUrl(request, redirectTo, { error: message }));
  }
}