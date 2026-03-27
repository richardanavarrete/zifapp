import { NextRequest } from "next/server"
import { authenticateOptional, errorResponse, jsonResponse } from "@/lib/api-utils"
import { parseBuffer } from "@/lib/services/parser-service"
import { SupabaseRepository } from "@/lib/supabase/repository"

export async function POST(request: NextRequest) {
  try {
    const ctx = await authenticateOptional(request)

    const formData = await request.formData()
    const file = formData.get("file") as File | null
    const name = formData.get("name") as string | null
    const skipRows = parseInt(formData.get("skip_rows") as string) || 0

    if (!file) return errorResponse("VALIDATION_ERROR", "No file provided")

    const ext = file.name.split(".").pop()?.toLowerCase()
    if (!ext || !["xlsx", "xls", "csv"].includes(ext)) {
      return errorResponse("VALIDATION_ERROR", `Unsupported file type: ${ext}. Use .xlsx, .xls, or .csv`)
    }

    // Parse file
    const buffer = await file.arrayBuffer()
    const { dataset, warnings } = parseBuffer(buffer, file.name, name ?? undefined, skipRows)

    // Persist to Supabase if authenticated with an org
    let persisted = false
    if (ctx?.orgId) {
      try {
        const repo = new SupabaseRepository(ctx.orgId)
        await repo.saveDataset(dataset)
        persisted = true
      } catch (e) {
        console.error("Failed to persist dataset:", e)
        return errorResponse(
          "PERSISTENCE_ERROR",
          `File parsed successfully (${dataset.items_count} items) but failed to save to database: ${e instanceof Error ? e.message : String(e)}`,
          500,
        )
      }
    }

    return jsonResponse({
      success: true,
      dataset_id: dataset.dataset_id,
      filename: file.name,
      items_count: dataset.items_count,
      records_count: dataset.records_count,
      periods_count: dataset.periods_count,
      categories_found: dataset.categories,
      warnings,
      persisted,
      ...((!persisted && ctx) ? { warning: "Data was parsed but not saved to the database. Please ensure you belong to an organization." } : {}),
    })
  } catch (e) {
    if (e instanceof Error && e.message.includes("Could not detect")) {
      return errorResponse("PARSE_ERROR", e.message)
    }
    console.error("Upload error:", e)
    return errorResponse("UPLOAD_ERROR", e instanceof Error ? e.message : "Upload failed", 500)
  }
}
