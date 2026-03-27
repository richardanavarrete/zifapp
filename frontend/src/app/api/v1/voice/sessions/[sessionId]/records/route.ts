import { NextRequest } from "next/server"
import { authenticate, errorResponse, jsonResponse } from "@/lib/api-utils"
import { SupabaseRepository } from "@/lib/supabase/repository"

function generateId(prefix: string): string {
  const hex = Array.from(crypto.getRandomValues(new Uint8Array(6)))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
  return `${prefix}_${hex}`
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  const result = await authenticate(request)
  if ("error" in result) return result.error
  const { ctx } = result

  if (!ctx.orgId) return errorResponse("NOT_FOUND", "Session not found", 404)

  const body = await request.json()
  const now = new Date().toISOString()
  const recordId = generateId("cr")

  const repo = new SupabaseRepository(ctx.orgId)

  await repo.saveVoiceRecord({
    record_id: recordId,
    session_id: sessionId,
    raw_text: body.raw_text,
    item_id: body.item_id ?? null,
    item_name: body.item_name ?? null,
    quantity: body.quantity ?? 1,
    unit: body.unit ?? "units",
    match_confidence: body.match_confidence ?? 0,
    confirmed: false,
    rejected: false,
    created_at: now,
  })

  return jsonResponse({
    record_id: recordId,
    session_id: sessionId,
    created_at: now,
    raw_text: body.raw_text,
    item_id: body.item_id ?? null,
    item_name: body.item_name ?? null,
    quantity: body.quantity ?? 1,
    unit: body.unit ?? "units",
    match_confidence: body.match_confidence ?? 0,
    match_method: body.match_method ?? null,
    confirmed: false,
    manually_edited: false,
  })
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  const result = await authenticate(request)
  if ("error" in result) return result.error
  const { ctx } = result

  if (!ctx.orgId) return jsonResponse([])

  const repo = new SupabaseRepository(ctx.orgId)
  const records = await repo.getVoiceRecords(sessionId)

  return jsonResponse(
    records.map((r) => ({
      record_id: r.record_id,
      session_id: r.session_id,
      created_at: r.created_at,
      raw_text: r.raw_text,
      item_id: r.item_id,
      item_name: r.item_name,
      quantity: r.quantity,
      unit: r.unit,
      match_confidence: r.match_confidence,
      match_method: null,
      confirmed: r.confirmed,
      manually_edited: false,
    })),
  )
}
