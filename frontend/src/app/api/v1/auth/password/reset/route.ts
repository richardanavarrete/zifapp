import { NextRequest } from "next/server"
import { getSupabaseClient } from "@/lib/supabase/server"
import { jsonResponse } from "@/lib/api-utils"

export async function POST(request: NextRequest) {
  const { email } = await request.json()
  if (email) {
    try {
      const client = getSupabaseClient()
      await client.auth.resetPasswordForEmail(email)
    } catch {
      // Don't reveal if email exists
    }
  }
  return jsonResponse({ message: "If an account exists with this email, a reset link has been sent." })
}
