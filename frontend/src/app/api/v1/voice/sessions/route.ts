import { NextRequest } from "next/server"
import { authenticate, errorResponse, jsonResponse } from "@/lib/api-utils"
import { SupabaseRepository } from "@/lib/supabase/repository"

function generateId(prefix: string): string {
  const hex = Array.from(crypto.getRandomValues(new Uint8Array(6)))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
  return `${prefix}_${hex}`
}

export async function POST(request: NextRequest) {
  const result = await authenticate(request)
  if ("error" in result) return result.error
  const { ctx } = result

  if (!ctx.orgId) return errorResponse("NO_ORG", "You must belong to an organization", 403)

  const body = await request.json()
  const { name, dataset_id, location, notes } = body

  if (!name) return errorResponse("VALIDATION_ERROR", "Session name is required")

  const now = new Date().toISOString()
  const sessionId = generateId("vs")

  const session = {
    session_id: sessionId,
    session_name: name,
    dataset_id: dataset_id ?? null,
    location: location ?? null,
    notes: notes ?? null,
    status: "in_progress",
    metadata: "{}",
    created_at: now,
    updated_at: now,
  }

  const repo = new SupabaseRepository(ctx.orgId)
  await repo.saveVoiceSession(session)

  return jsonResponse({
    session_id: sessionId,
    name,
    created_at: now,
    updated_at: now,
    status: "in_progress",
    dataset_id: dataset_id ?? null,
    location: location ?? null,
    notes: notes ?? null,
    items_counted: 0,
    total_units: 0,
  })
}

export async function GET(request: NextRequest) {
  const result = await authenticate(request)
  if ("error" in result) return result.error
  const { ctx } = result

  if (!ctx.orgId) return jsonResponse([])

  const repo = new SupabaseRepository(ctx.orgId)
  const sessions = await repo.getVoiceSessions()

  const { searchParams } = new URL(request.url)
  const status = searchParams.get("status")

  let filtered = sessions
  if (status) {
    filtered = sessions.filter((s) => s.status === status)
  }

  return jsonResponse(
    filtered.map((s) => ({
      session_id: s.session_id,
      name: s.session_name,
      created_at: s.created_at,
      updated_at: s.updated_at,
      status: s.status,
      dataset_id: s.dataset_id,
      location: s.location,
      notes: s.notes,
      items_counted: 0,
      total_units: 0,
    })),
  )
}
