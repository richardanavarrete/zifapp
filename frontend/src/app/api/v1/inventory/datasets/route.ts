import { NextRequest } from "next/server"
import { authenticateOptional, jsonResponse } from "@/lib/api-utils"
import { SupabaseRepository } from "@/lib/supabase/repository"

export async function GET(request: NextRequest) {
  const ctx = await authenticateOptional(request)

  if (ctx?.orgId) {
    const repo = new SupabaseRepository(ctx.orgId)
    const datasets = await repo.listDatasets()
    return jsonResponse({ datasets })
  }

  return jsonResponse({ datasets: [] })
}
