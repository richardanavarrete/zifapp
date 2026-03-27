import { NextRequest } from "next/server"
import { authenticateOptional, errorResponse, jsonResponse } from "@/lib/api-utils"
import { SupabaseRepository } from "@/lib/supabase/repository"
import type { ParsedDataset, ParsedItem, ParsedRecord } from "@/lib/services/parser-service"

function generateId(prefix: string): string {
  const hex = Array.from(crypto.getRandomValues(new Uint8Array(6)))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
  return `${prefix}_${hex}`
}

function makeItemId(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 50)
}

export async function POST(request: NextRequest) {
  try {
    const ctx = await authenticateOptional(request)
    const body = await request.json()
    const { dataset_id, dataset_name, items } = body

    if (!dataset_id && !dataset_name) {
      return errorResponse("VALIDATION_ERROR", "Either dataset_id or dataset_name is required")
    }
    if (!items || !Array.isArray(items) || items.length === 0) {
      return errorResponse("VALIDATION_ERROR", "At least one item is required")
    }

    const today = new Date().toISOString().split("T")[0]
    const now = new Date().toISOString()
    const warnings: string[] = []

    const parsedItems: Record<string, ParsedItem> = {}
    const records: ParsedRecord[] = []
    let itemsAdded = 0

    for (const entry of items) {
      const itemId = makeItemId(entry.name)
      const recordDate = entry.record_date || today

      if (!parsedItems[itemId]) {
        parsedItems[itemId] = {
          item_id: itemId,
          name: entry.name,
          category: entry.category,
          vendor: entry.vendor,
          sku: entry.sku,
          unit_cost: entry.unit_cost,
          unit_of_measure: entry.unit_of_measure || "unit",
        }
        itemsAdded++
      } else {
        warnings.push(`Item '${entry.name}' already exists, updated record`)
      }

      records.push({
        record_id: generateId("r"),
        item_id: itemId,
        record_date: recordDate,
        on_hand: entry.on_hand ?? 0,
        source_file: "manual_entry",
      })
    }

    const categories = [...new Set(Object.values(parsedItems).map((i) => i.category).filter(Boolean))] as string[]
    const dates = [...new Set(records.map((r) => r.record_date))].sort()

    const dsId = dataset_id || generateId("ds")
    const dsName = dataset_name || "Manual Entry"

    const dataset: ParsedDataset = {
      dataset_id: dsId,
      name: dsName,
      created_at: now,
      source_files: ["manual_entry"],
      date_range_start: dates[0],
      date_range_end: dates[dates.length - 1],
      items_count: Object.keys(parsedItems).length,
      records_count: records.length,
      periods_count: dates.length,
      categories,
      vendors: [...new Set(Object.values(parsedItems).map((i) => i.vendor).filter(Boolean))] as string[],
      items: parsedItems,
      records,
    }

    // Persist
    if (ctx?.orgId) {
      const repo = new SupabaseRepository(ctx.orgId)
      await repo.saveDataset(dataset)
    }

    return jsonResponse({
      success: true,
      dataset_id: dsId,
      dataset_name: dsName,
      items_added: itemsAdded,
      records_added: records.length,
      categories_found: categories,
      warnings,
      created_at: now,
    })
  } catch (e) {
    console.error("Manual entry error:", e)
    return errorResponse("MANUAL_ENTRY_ERROR", e instanceof Error ? e.message : "Failed", 500)
  }
}
