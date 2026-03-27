import { authenticate, errorResponse, jsonResponse } from "@/lib/api-utils"
import { getSupabaseAdminClient } from "@/lib/supabase/server"

export async function GET(request: Request) {
  const result = await authenticate(request)
  if ("error" in result) return result.error
  const { ctx } = result

  const admin = getSupabaseAdminClient()

  const { data: profile } = await admin
    .from("user_profiles")
    .select("*")
    .eq("user_id", ctx.userId)
    .maybeSingle()

  let orgName: string | null = null
  let orgRole: string | null = null

  if (ctx.orgId) {
    const { data: membership } = await admin
      .from("organization_members")
      .select("role, organizations(name)")
      .eq("user_id", ctx.userId)
      .eq("org_id", ctx.orgId)
      .maybeSingle()

    if (membership) {
      orgRole = membership.role
      const orgData = membership.organizations as unknown as { name: string } | null
      orgName = orgData?.name ?? null
    }
  }

  return jsonResponse({
    user_id: ctx.userId,
    email: ctx.email,
    full_name: profile?.full_name ?? null,
    org_id: ctx.orgId,
    org_name: orgName,
    org_role: orgRole,
  })
}
