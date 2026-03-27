import { NextRequest } from "next/server"
import { getSupabaseClient, getSupabaseAdminClient } from "@/lib/supabase/server"
import { errorResponse, jsonResponse } from "@/lib/api-utils"

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { email, password, full_name, organization_name, invite_code } = body

    if (!email || !password) {
      return errorResponse("VALIDATION_ERROR", "Email and password are required")
    }

    const client = getSupabaseClient()

    // Register with Supabase Auth
    const { data: authData, error: authError } = await client.auth.signUp({
      email,
      password,
      options: { data: { full_name } },
    })

    if (authError) {
      if (authError.message.toLowerCase().includes("already registered")) {
        return errorResponse("EMAIL_EXISTS", "Email already registered")
      }
      return errorResponse("REGISTRATION_FAILED", authError.message)
    }

    if (!authData.user || !authData.session) {
      return errorResponse("REGISTRATION_FAILED", "Registration failed")
    }

    const admin = getSupabaseAdminClient()
    const userId = authData.user.id
    const now = new Date().toISOString()

    // Create user profile
    await admin.from("user_profiles").insert({
      user_id: userId,
      email,
      full_name: full_name ?? null,
      created_at: now,
      updated_at: now,
    })

    let orgId: string | null = null
    let orgName: string | null = null
    let orgRole: string | null = null

    // Create organization if requested
    if (organization_name) {
      const slug = organization_name
        .toLowerCase()
        .replace(/[^a-z0-9\s-]/g, "")
        .replace(/[\s_-]+/g, "-")
        .replace(/^-|-$/g, "")
      const orgIdVal = crypto.randomUUID()

      await admin.from("organizations").insert({
        id: orgIdVal,
        name: organization_name,
        slug: `${slug}-${orgIdVal.slice(0, 6)}`,
        owner_id: userId,
        plan: "free",
        created_at: now,
        updated_at: now,
      })

      await admin.from("organization_members").insert({
        org_id: orgIdVal,
        user_id: userId,
        role: "owner",
        joined_at: now,
      })

      orgId = orgIdVal
      orgName = organization_name
      orgRole = "owner"
    } else if (invite_code) {
      // Accept invite
      const { data: invite } = await admin
        .from("organization_invites")
        .select("*")
        .eq("code", invite_code)
        .eq("accepted", false)
        .single()

      if (invite) {
        const expires = new Date(invite.expires_at)
        if (expires > new Date()) {
          await admin.from("organization_members").insert({
            org_id: invite.org_id,
            user_id: userId,
            role: invite.role,
            joined_at: now,
          })
          await admin
            .from("organization_invites")
            .update({ accepted: true })
            .eq("id", invite.id)

          orgId = invite.org_id
          orgRole = invite.role

          const { data: org } = await admin
            .from("organizations")
            .select("name")
            .eq("id", invite.org_id)
            .single()
          orgName = org?.name ?? null
        }
      }
    }

    return jsonResponse(
      {
        user: {
          id: userId,
          email,
          full_name,
          created_at: authData.user.created_at,
        },
        profile: {
          user_id: userId,
          email,
          full_name,
          org_id: orgId,
          org_name: orgName,
          org_role: orgRole,
          created_at: now,
        },
        tokens: {
          access_token: authData.session.access_token,
          refresh_token: authData.session.refresh_token,
          token_type: "bearer",
          expires_in: authData.session.expires_in ?? 3600,
          expires_at: authData.session.expires_at,
        },
      },
      201,
    )
  } catch (e) {
    console.error("Registration error:", e)
    return errorResponse("REGISTRATION_FAILED", "An unexpected error occurred during registration.", 500)
  }
}
