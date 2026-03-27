import { NextRequest } from "next/server"
import { authenticateOptional, errorResponse, jsonResponse } from "@/lib/api-utils"
import { SupabaseRepository } from "@/lib/supabase/repository"
import { computeAllStats } from "@/lib/services/stats-service"
import { generateRecommendations } from "@/lib/services/order-service"

export async function POST(request: NextRequest) {
  const ctx = await authenticateOptional(request)
  const body = await request.json()
  const { dataset_id } = body

  if (!dataset_id) return errorResponse("VALIDATION_ERROR", "dataset_id is required")
  if (!ctx?.orgId) return errorResponse("NOT_FOUND", "Dataset not found", 404)

  const repo = new SupabaseRepository(ctx.orgId)
  const dataset = await repo.getDataset(dataset_id)
  if (!dataset) return errorResponse("NOT_FOUND", "Dataset not found", 404)

  const allStats = computeAllStats(dataset.items, dataset.records)
  const run = generateRecommendations(dataset.items, allStats, dataset_id, body)

  return jsonResponse(run)
}
