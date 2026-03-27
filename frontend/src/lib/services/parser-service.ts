/**
 * Parser Service - Handles spreadsheet parsing
 *
 * Auto-detects column mappings and parses inventory sheets.
 * Port of smallcogs/services/parser_service.py
 */

import * as XLSX from "xlsx"

// ============== Types ==============

export interface ParsedItem {
  item_id: string
  name: string
  category?: string
  vendor?: string
  sku?: string
  unit_cost?: number
  unit_of_measure: string
  location?: string
}

export interface ParsedRecord {
  record_id: string
  item_id: string
  record_date: string // ISO date
  on_hand: number
  usage?: number
  period_name?: string
  source_file?: string
}

export interface ParsedDataset {
  dataset_id: string
  name: string
  created_at: string
  source_files: string[]
  date_range_start?: string
  date_range_end?: string
  items_count: number
  records_count: number
  periods_count: number
  categories: string[]
  vendors: string[]
  items: Record<string, ParsedItem>
  records: ParsedRecord[]
}

export interface ParseResult {
  dataset: ParsedDataset
  warnings: string[]
}

// ============== Column detection patterns ==============

const ITEM_PATTERNS = [/^item/i, /^product/i, /^name/i, /^description/i, /^sku/i, /^material/i, /^inventory.?item/i]
const COUNT_PATTERNS = [/^on.?hand/i, /^qty/i, /^quantity/i, /^count/i, /^stock/i, /^ending/i, /^end.?inv/i, /^current/i, /^balance/i]
const USAGE_PATTERNS = [/^usage/i, /^used/i, /^consumed/i, /^sold/i, /^movement/i]
const CATEGORY_PATTERNS = [/^category/i, /^type/i, /^group/i, /^class/i, /^dept/i]
const DATE_PATTERNS = [/^date/i, /^week/i, /^period/i, /^time/i]
const VENDOR_PATTERNS = [/^vendor/i, /^supplier/i, /^source/i]

function findMatch(columns: string[], patterns: RegExp[]): string | null {
  for (const col of columns) {
    for (const pattern of patterns) {
      if (pattern.test(col)) return col
    }
  }
  return null
}

function makeItemId(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "")
    .slice(0, 50)
}

function generateId(prefix: string): string {
  const hex = Array.from(crypto.getRandomValues(new Uint8Array(6)))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
  return `${prefix}_${hex}`
}

// ============== Main parser ==============

export function parseBuffer(
  buffer: ArrayBuffer,
  filename: string,
  datasetName?: string,
  skipRows = 0,
): ParseResult {
  const warnings: string[] = []

  // Read workbook
  const workbook = XLSX.read(buffer, { type: "array", cellDates: true })

  // Select sheet
  let sheetName = workbook.SheetNames[0]
  if (workbook.SheetNames.length > 1) {
    const found = workbook.SheetNames.find((name) =>
      ["inventory", "data", "sheet1"].some((kw) => name.toLowerCase().includes(kw)),
    )
    if (found) {
      sheetName = found
      warnings.push(`Auto-selected sheet: ${found}`)
    } else {
      warnings.push(`Using first sheet: ${sheetName}`)
    }
  }

  const sheet = workbook.Sheets[sheetName]
  const rows: Record<string, unknown>[] = XLSX.utils.sheet_to_json(sheet, {
    range: skipRows,
    defval: null,
  })

  if (rows.length === 0) {
    throw new Error("File contains no data")
  }

  // Get column names
  const columns = Object.keys(rows[0])

  // Auto-detect columns
  const itemCol = findMatch(columns, ITEM_PATTERNS)
  const onHandCol = findMatch(columns, COUNT_PATTERNS)
  const usageCol = findMatch(columns, USAGE_PATTERNS)
  const categoryCol = findMatch(columns, CATEGORY_PATTERNS)
  const dateCol = findMatch(columns, DATE_PATTERNS)
  const vendorCol = findMatch(columns, VENDOR_PATTERNS)

  if (!itemCol) {
    throw new Error("Could not detect item/product name column")
  }

  // Parse data
  const items: Record<string, ParsedItem> = {}
  const records: ParsedRecord[] = []
  const today = new Date().toISOString().split("T")[0]

  for (const row of rows) {
    const rawName = row[itemCol]
    if (!rawName || String(rawName).trim() === "" || String(rawName).toUpperCase().includes("TOTAL")) {
      continue
    }

    const itemName = String(rawName).trim()
    const itemId = makeItemId(itemName)

    // Create item if new
    if (!items[itemId]) {
      items[itemId] = {
        item_id: itemId,
        name: itemName,
        category: categoryCol ? safeString(row[categoryCol]) : undefined,
        vendor: vendorCol ? safeString(row[vendorCol]) : undefined,
        unit_of_measure: "unit",
      }
    }

    // Parse date
    let recordDate = today
    if (dateCol && row[dateCol]) {
      try {
        const d = row[dateCol]
        if (d instanceof Date) {
          recordDate = d.toISOString().split("T")[0]
        } else {
          const parsed = new Date(String(d))
          if (!isNaN(parsed.getTime())) {
            recordDate = parsed.toISOString().split("T")[0]
          }
        }
      } catch {
        // keep default
      }
    }

    // Parse on_hand
    let onHand = 0
    if (onHandCol && row[onHandCol] != null) {
      const parsed = parseFloat(String(row[onHandCol]))
      if (!isNaN(parsed)) onHand = parsed
    }

    // Parse usage
    let usage: number | undefined
    if (usageCol && row[usageCol] != null) {
      const parsed = parseFloat(String(row[usageCol]))
      if (!isNaN(parsed)) {
        usage = parsed
        if (parsed < 0) {
          warnings.push(`Negative usage for ${itemName}: ${parsed}`)
        }
      }
    }

    records.push({
      record_id: generateId("r"),
      item_id: itemId,
      record_date: recordDate,
      on_hand: onHand,
      usage,
      source_file: filename,
    })
  }

  // Build dataset
  const dates = [...new Set(records.map((r) => r.record_date))].sort()
  const categories = [
    ...new Set(
      Object.values(items)
        .map((i) => i.category)
        .filter(Boolean),
    ),
  ].sort() as string[]
  const vendors = [
    ...new Set(
      Object.values(items)
        .map((i) => i.vendor)
        .filter(Boolean),
    ),
  ].sort() as string[]

  const dataset: ParsedDataset = {
    dataset_id: generateId("ds"),
    name: datasetName || filename.replace(/\.[^.]+$/, ""),
    created_at: new Date().toISOString(),
    source_files: [filename],
    date_range_start: dates[0] ?? undefined,
    date_range_end: dates[dates.length - 1] ?? undefined,
    items_count: Object.keys(items).length,
    records_count: records.length,
    periods_count: dates.length,
    categories,
    vendors,
    items,
    records,
  }

  return { dataset, warnings }
}

function safeString(value: unknown): string | undefined {
  if (value == null) return undefined
  const s = String(value).trim()
  return s || undefined
}
