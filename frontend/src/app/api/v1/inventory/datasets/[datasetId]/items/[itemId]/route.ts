import { NextRequest } from "next/server"
import { authenticateOptional, errorResponse, jsonResponse } from "@/lib/api-utils"
import { SupabaseRepository } from "@/lib/supabase/repository"
import { getItemDetail } from "@/lib/services/stats-service"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ datasetId: string; itemId: string }> },
) {
  const { datasetId, itemId } = await params
  const ctx = await authenticateOptional(request)

  if (!ctx?.orgId) return errorResponse("NOT_FOUND", "Item not found", 404)

  const repo = new SupabaseRepository(ctx.orgId)
  const dataset = await repo.getDataset(datasetId)
  if (!dataset) return errorResponse("NOT_FOUND", "Dataset not found", 404)

  const item = dataset.items[itemId]
  if (!item) return errorResponse("NOT_FOUND", "Item not found", 404)

  const detail = getItemDetail(item, dataset.records)
  return jsonResponse(detail)
}
