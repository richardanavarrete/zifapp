import { NextRequest } from "next/server"
import { authenticate, errorResponse, jsonResponse } from "@/lib/api-utils"
import { getSupabaseAdminClient } from "@/lib/supabase/server"

export async function POST(request: NextRequest) {
  const result = await authenticate(request)
  if ("error" in result) return result.error
  const { ctx } = result

  if (ctx.orgId) {
    return errorResponse("ALREADY_IN_ORG", "You already belong to an organization. Leave your current org first.")
  }

  const { name, slug: customSlug } = await request.json()
  if (!name) return errorResponse("VALIDATION_ERROR", "Organization name is required")

  const admin = getSupabaseAdminClient()
  const now = new Date().toISOString()
  const orgId = crypto.randomUUID()

  const slug =
    customSlug ||
    name
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, "")
      .replace(/[\s_-]+/g, "-")
      .replace(/^-|-$/g, "") +
      "-" +
      orgId.slice(0, 6)

  await admin.from("organizations").insert({
    id: orgId,
    name,
    slug,
    owner_id: ctx.userId,
    plan: "free",
    created_at: now,
    updated_at: now,
  })

  await admin.from("organization_members").insert({
    org_id: orgId,
    user_id: ctx.userId,
    role: "owner",
    joined_at: now,
  })

  return jsonResponse(
    { id: orgId, name, slug, plan: "free", created_at: now, owner_id: ctx.userId },
    201,
  )
}
