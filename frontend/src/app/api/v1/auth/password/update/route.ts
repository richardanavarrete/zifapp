import { NextRequest } from "next/server"
import { authenticate, errorResponse, jsonResponse } from "@/lib/api-utils"
import { getSupabaseClient } from "@/lib/supabase/server"

export async function POST(request: NextRequest) {
  const result = await authenticate(request)
  if ("error" in result) return result.error

  const { password } = await request.json()
  if (!password) return errorResponse("VALIDATION_ERROR", "Password is required")

  try {
    const client = getSupabaseClient()
    const { error } = await client.auth.updateUser({ password })
    if (error) return errorResponse("PASSWORD_UPDATE_FAILED", error.message)
    return jsonResponse({ message: "Password updated successfully" })
  } catch (e) {
    console.error("Password update error:", e)
    return errorResponse("PASSWORD_UPDATE_FAILED", "An unexpected error occurred.", 500)
  }
}
