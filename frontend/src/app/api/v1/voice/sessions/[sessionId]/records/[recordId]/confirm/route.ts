import { NextRequest } from "next/server"
import { authenticate, errorResponse, jsonResponse } from "@/lib/api-utils"
import { getSupabaseAdminClient } from "@/lib/supabase/server"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string; recordId: string }> },
) {
  const { recordId } = await params
  const result = await authenticate(request)
  if ("error" in result) return result.error

  const admin = getSupabaseAdminClient()
  const { error } = await admin
    .from("voice_count_records")
    .update({ confirmed: true })
    .eq("record_id", recordId)

  if (error) return errorResponse("UPDATE_ERROR", error.message, 500)

  return jsonResponse({ status: "confirmed" })
}
