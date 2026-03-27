import { jsonResponse } from "@/lib/api-utils"
import { DEFAULT_TARGETS } from "@/lib/services/order-service"

export async function GET() {
  return jsonResponse(DEFAULT_TARGETS)
}
