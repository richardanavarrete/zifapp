import { NextRequest } from "next/server"
import { authenticate, errorResponse, jsonResponse } from "@/lib/api-utils"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ runId: string }> },
) {
  const { runId } = await params
  const result = await authenticate(request)
  if ("error" in result) return result.error

  // TODO: Apply approval changes to the run
  return jsonResponse({ status: "approved", run_id: runId })
}
