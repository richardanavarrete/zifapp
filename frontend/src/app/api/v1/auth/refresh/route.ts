import { NextRequest } from "next/server"
import { getSupabaseClient } from "@/lib/supabase/server"
import { errorResponse, jsonResponse } from "@/lib/api-utils"

export async function POST(request: NextRequest) {
  try {
    const { refresh_token } = await request.json()
    if (!refresh_token) {
      return errorResponse("VALIDATION_ERROR", "refresh_token is required")
    }

    const client = getSupabaseClient()
    const { data, error } = await client.auth.refreshSession({ refresh_token })

    if (error || !data.session) {
      return errorResponse("INVALID_REFRESH_TOKEN", "Invalid refresh token", 401)
    }

    return jsonResponse({
      access_token: data.session.access_token,
      refresh_token: data.session.refresh_token,
      token_type: "bearer",
      expires_in: data.session.expires_in ?? 3600,
      expires_at: data.session.expires_at,
    })
  } catch (e) {
    console.error("Token refresh error:", e)
    return errorResponse("REFRESH_FAILED", "An unexpected error occurred during token refresh.", 500)
  }
}
