import { NextRequest } from "next/server"
import { authenticateOptional, errorResponse, jsonResponse } from "@/lib/api-utils"
import { SupabaseRepository } from "@/lib/supabase/repository"
import { matchText } from "@/lib/services/voice-service"

export async function POST(request: NextRequest) {
  const ctx = await authenticateOptional(request)
  const body = await request.json()

  const { text, dataset_id, confidence_threshold, max_alternatives } = body

  if (!text) return errorResponse("VALIDATION_ERROR", "text is required")

  let items: Record<string, import("@/lib/services/parser-service").ParsedItem> = {}

  if (dataset_id && ctx?.orgId) {
    const repo = new SupabaseRepository(ctx.orgId)
    const dataset = await repo.getDataset(dataset_id)
    if (dataset) {
      items = dataset.items
    }
  }

  const result = matchText(text, items, confidence_threshold ?? 0.7, max_alternatives ?? 3)

  // The frontend expects a single ParsedVoiceInput, not a list - match the existing API contract
  if (result.parsed_items.length === 1) {
    return jsonResponse(result.parsed_items[0])
  }

  return jsonResponse(result)
}
