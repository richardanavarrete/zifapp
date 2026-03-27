import { NextRequest } from "next/server"
import { authenticateOptional, errorResponse, jsonResponse } from "@/lib/api-utils"
import { SupabaseRepository } from "@/lib/supabase/repository"
import { computeItemStats } from "@/lib/services/stats-service"

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

  const { searchParams } = new URL(request.url)
  const search = searchParams.get("search")?.toLowerCase()
  const category = searchParams.get("category")
  const vendor = searchParams.get("vendor")

  let itemList = Object.values(dataset.items)

  if (search) {
    itemList = itemList.filter((i) => i.name.toLowerCase().includes(search))
  }
  if (category) {
    itemList = itemList.filter((i) => i.category === category)
  }
  if (vendor) {
    itemList = itemList.filter((i) => i.vendor === vendor)
  }

  const items = itemList.map((item) => {
    const itemRecords = dataset.records.filter((r) => r.item_id === item.item_id)
    const stats = computeItemStats(item, itemRecords)
    return { ...item, stats }
  })

  return jsonResponse({ items, count: items.length })
}
