import { jsonResponse } from "@/lib/api-utils"
import { DEFAULT_CONSTRAINTS } from "@/lib/services/order-service"

export async function GET() {
  return jsonResponse(DEFAULT_CONSTRAINTS)
}
