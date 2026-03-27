import { NextRequest } from "next/server"
import { authenticate, errorResponse, jsonResponse } from "@/lib/api-utils"
import { SupabaseRepository } from "@/lib/supabase/repository"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  const result = await authenticate(request)
  if ("error" in result) return result.error
  const { ctx } = result

  if (!ctx.orgId) return errorResponse("NOT_FOUND", "Session not found", 404)

  const repo = new SupabaseRepository(ctx.orgId)
  const session = await repo.getVoiceSession(sessionId)
  if (!session) return errorResponse("NOT_FOUND", "Session not found", 404)

  await repo.saveVoiceSession({
    ...session,
    status: "completed",
    updated_at: new Date().toISOString(),
  })

  return jsonResponse({
    session_id: session.session_id,
    name: session.session_name,
    created_at: session.created_at,
    updated_at: new Date().toISOString(),
    status: "completed",
    dataset_id: session.dataset_id,
    location: session.location,
    notes: session.notes,
    items_counted: 0,
    total_units: 0,
  })
}
