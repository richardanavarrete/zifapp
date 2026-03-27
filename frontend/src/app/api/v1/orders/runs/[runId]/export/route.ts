import { NextRequest } from "next/server"
import { authenticate, errorResponse, jsonResponse } from "@/lib/api-utils"
import { SupabaseRepository } from "@/lib/supabase/repository"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ runId: string }> },
) {
  const { runId } = await params
  const result = await authenticate(request)
  if ("error" in result) return result.error
  const { ctx } = result

  if (!ctx.orgId) return errorResponse("NOT_FOUND", "Run not found", 404)

  const repo = new SupabaseRepository(ctx.orgId)
  const run = await repo.getAgentRun(runId)
  if (!run) return errorResponse("NOT_FOUND", "Run not found", 404)

  // Return the run data - the frontend can format as needed
  return jsonResponse(run)
}
