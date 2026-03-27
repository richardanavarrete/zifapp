import { NextRequest } from "next/server"
import { authenticateOptional, errorResponse, jsonResponse } from "@/lib/api-utils"
import { SupabaseRepository } from "@/lib/supabase/repository"
import { computeAllStats, getCategorySummary } from "@/lib/services/stats-service"

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

  const allStats = computeAllStats(dataset.items, dataset.records)
  const categorySummary = getCategorySummary(allStats)

  const statsValues = Object.values(allStats)
  const totalItems = statsValues.length
  const totalOnHand = statsValues.reduce((s, v) => s + v.current_on_hand, 0)

  const lowStock = statsValues.filter((s) => s.weeks_on_hand != null && s.weeks_on_hand < 1)
  const trendingUp = statsValues.filter((s) => s.trend_direction === "up")
  const trendingDown = statsValues.filter((s) => s.trend_direction === "down")
  const dataIssues = statsValues.filter((s) => s.has_negative_usage || s.has_gaps)

  return jsonResponse({
    dataset_id: datasetId,
    dataset_name: dataset.name,
    total_items: totalItems,
    total_on_hand: totalOnHand,
    periods_count: dataset.periods_count,
    date_range: {
      start: dataset.date_range_start,
      end: dataset.date_range_end,
    },
    categories: categorySummary,
    alerts: {
      low_stock_count: lowStock.length,
      low_stock_items: lowStock.slice(0, 5).map((s) => s.item_name),
      trending_up_count: trendingUp.length,
      trending_down_count: trendingDown.length,
      data_issues_count: dataIssues.length,
    },
  })
}
