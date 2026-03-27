import { NextRequest } from "next/server"
import { authenticateOptional, errorResponse, jsonResponse } from "@/lib/api-utils"
import { SupabaseRepository } from "@/lib/supabase/repository"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ datasetId: string }> },
) {
  const { datasetId } = await params
  const ctx = await authenticateOptional(request)

  if (!ctx?.orgId) return errorResponse("NOT_FOUND", "Dataset not found", 404)

  const repo = new SupabaseRepository(ctx.orgId)
  const dataset = await repo.getDataset(datasetId)
  if (!dataset) return errorResponse("NOT_FOUND", "Dataset not found", 404)

  return jsonResponse({
    dataset_id: dataset.dataset_id,
    name: dataset.name,
    created_at: dataset.created_at,
    items_count: dataset.items_count,
    records_count: dataset.records_count,
    periods_count: dataset.periods_count,
    date_range_start: dataset.date_range_start,
    date_range_end: dataset.date_range_end,
    categories: dataset.categories,
    vendors: dataset.vendors,
  })
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ datasetId: string }> },
) {
  const { datasetId } = await params
  const ctx = await authenticateOptional(request)

  if (!ctx?.orgId) return errorResponse("NOT_FOUND", "Dataset not found", 404)

  const repo = new SupabaseRepository(ctx.orgId)
  const deleted = await repo.deleteDataset(datasetId)
  if (!deleted) return errorResponse("NOT_FOUND", "Dataset not found", 404)

  return jsonResponse({ deleted: true })
}
