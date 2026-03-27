import { NextRequest } from "next/server"
import { authenticate, jsonResponse } from "@/lib/api-utils"
import { SupabaseRepository } from "@/lib/supabase/repository"

export async function GET(request: NextRequest) {
  const result = await authenticate(request)
  if ("error" in result) return result.error
  const { ctx } = result

  if (!ctx.orgId) return jsonResponse([])

  const { searchParams } = new URL(request.url)
  const datasetId = searchParams.get("dataset_id") ?? undefined

  const repo = new SupabaseRepository(ctx.orgId)
  const runs = await repo.getAgentRuns(datasetId)

  return jsonResponse(runs)
}
