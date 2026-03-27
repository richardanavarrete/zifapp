import { NextRequest } from "next/server"
import { getSupabaseClient, getSupabaseAdminClient } from "@/lib/supabase/server"
import { errorResponse, jsonResponse } from "@/lib/api-utils"

export async function POST(request: NextRequest) {
  try {
    const { email, password } = await request.json()

    if (!email || !password) {
      return errorResponse("VALIDATION_ERROR", "Email and password are required")
    }

    const client = getSupabaseClient()
    const { data, error } = await client.auth.signInWithPassword({ email, password })

    if (error || !data.user || !data.session) {
      return errorResponse("INVALID_CREDENTIALS", "Invalid email or password", 401)
    }

    const userId = data.user.id
    const userMeta = data.user.user_metadata ?? {}

    // Get profile with org info
    const admin = getSupabaseAdminClient()

    const { data: profile } = await admin
      .from("user_profiles")
      .select("*")
      .eq("user_id", userId)
      .maybeSingle()

    let orgId: string | null = null
    let orgName: string | null = null
    let orgRole: string | null = null

    const { data: membership } = await admin
      .from("organization_members")
      .select("org_id, role, organizations(id, name)")
      .eq("user_id", userId)
      .maybeSingle()

    if (membership) {
      orgId = membership.org_id
      orgRole = membership.role
      const orgData = membership.organizations as unknown as { id: string; name: string } | null
      orgName = orgData?.name ?? null
    }

    const fullName = profile?.full_name ?? userMeta.full_name ?? null

    // Create profile if it doesn't exist
    if (!profile) {
      const now = new Date().toISOString()
      await admin.from("user_profiles").insert({
        user_id: userId,
        email,
        full_name: fullName,
        created_at: now,
        updated_at: now,
      })
    }

    return jsonResponse({
      user: {
        id: userId,
        email,
        full_name: fullName,
        created_at: data.user.created_at,
        updated_at: data.user.updated_at,
      },
      profile: {
        user_id: userId,
        email,
        full_name: fullName,
        avatar_url: profile?.avatar_url ?? null,
        org_id: orgId,
        org_name: orgName,
        org_role: orgRole,
        created_at: profile?.created_at ?? data.user.created_at,
        updated_at: profile?.updated_at ?? null,
      },
      tokens: {
        access_token: data.session.access_token,
        refresh_token: data.session.refresh_token,
        token_type: "bearer",
        expires_in: data.session.expires_in ?? 3600,
        expires_at: data.session.expires_at,
      },
    })
  } catch (e) {
    console.error("Login error:", e)
    return errorResponse("LOGIN_FAILED", "An unexpected error occurred during login.", 500)
  }
}
