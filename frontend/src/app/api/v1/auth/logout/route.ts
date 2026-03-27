import { jsonResponse } from "@/lib/api-utils"

export async function POST() {
  return jsonResponse({ message: "Logged out successfully" })
}
