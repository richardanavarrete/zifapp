/**
 * Order Recommendation Service
 *
 * Generates smart order recommendations based on usage patterns.
 * Port of smallcogs/services/order_service.py
 */

import type { ItemStats } from "./stats-service"
import type { ParsedItem } from "./parser-service"

// ============== Types ==============

export type ReasonCode =
  | "stockout_risk"
  | "low_stock"
  | "trending_up"
  | "trending_down"
  | "below_target"
  | "overstock"
  | "reorder_point"
  | "data_quality"

export type Confidence = "high" | "medium" | "low"

export interface OrderTargets {
  default_weeks: number
  by_category: Record<string, number>
  by_item: Record<string, number>
  exclude_items: string[]
}

export interface OrderConstraints {
  max_spend?: number
  max_items?: number
  vendor_minimums: Record<string, number>
  vendor_maximums: Record<string, number>
  low_stock_weeks: number
  overstock_weeks: number
}

export interface SalesForecast {
  percent_change?: number
  expected_total_sales?: number
  historical_avg_total_sales?: number
  by_category: Record<string, number>
  historical_by_category: Record<string, number>
  forecast_weeks: number
  notes?: string
}

export interface Recommendation {
  item_id: string
  item_name: string
  category?: string
  vendor?: string
  on_hand: number
  avg_usage: number
  weeks_on_hand: number | null
  suggested_qty: number
  unit_cost?: number
  total_cost?: number
  reason: ReasonCode
  reason_text: string
  confidence: Confidence
  trend_direction?: string
  trend_pct?: number
  forecast_multiplier?: number
  base_suggested_qty?: number
  warnings: string[]
}

export interface RecommendationRun {
  run_id: string
  dataset_id: string
  created_at: string
  targets: OrderTargets
  constraints: OrderConstraints
  forecast?: SalesForecast
  recommendations: Recommendation[]
  total_items: number
  total_spend: number
  low_stock_count: number
  overstock_count: number
  by_vendor: Record<string, { items: number; spend: number }>
  by_category: Record<string, { items: number; spend: number }>
  by_reason: Record<string, number>
  warnings: string[]
  data_issues: { item_id: string; item_name: string; issues: string[] }[]
  status: string
}

export interface RecommendRequest {
  dataset_id: string
  targets?: OrderTargets
  constraints?: OrderConstraints
  forecast?: SalesForecast
  categories?: string[]
  vendors?: string[]
  exclude_items?: string[]
}

// ============== Defaults ==============

export const DEFAULT_TARGETS: OrderTargets = {
  default_weeks: 2,
  by_category: {},
  by_item: {},
  exclude_items: [],
}

export const DEFAULT_CONSTRAINTS: OrderConstraints = {
  vendor_minimums: {},
  vendor_maximums: {},
  low_stock_weeks: 1,
  overstock_weeks: 8,
}

// ============== Logic ==============

function getTarget(targets: OrderTargets, itemId: string, category?: string): number {
  if (targets.exclude_items.includes(itemId)) return 0
  if (targets.by_item[itemId] != null) return targets.by_item[itemId]
  if (category && targets.by_category[category] != null) return targets.by_category[category]
  return targets.default_weeks
}

function getForecastMultiplier(forecast: SalesForecast | undefined, category?: string): number {
  if (!forecast) return 1.0
  if (forecast.percent_change != null) return 1.0 + forecast.percent_change / 100
  if (category && forecast.by_category[category] != null && forecast.historical_by_category[category]) {
    return forecast.by_category[category] / forecast.historical_by_category[category]
  }
  if (forecast.expected_total_sales != null && forecast.historical_avg_total_sales) {
    return forecast.expected_total_sales / forecast.historical_avg_total_sales
  }
  return 1.0
}

function generateId(prefix: string): string {
  const hex = Array.from(crypto.getRandomValues(new Uint8Array(6)))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
  return `${prefix}_${hex}`
}

function determineReason(
  stats: ItemStats,
  targetWeeks: number,
  constraints: OrderConstraints,
): { reason: ReasonCode; reasonText: string; confidence: Confidence } {
  const woh = stats.weeks_on_hand ?? 0

  if (woh < constraints.low_stock_weeks) {
    if (woh < 0.5) {
      return { reason: "stockout_risk", reasonText: `Critical: only ${woh.toFixed(1)} weeks on hand`, confidence: "high" }
    }
    return { reason: "low_stock", reasonText: `Low stock: ${woh.toFixed(1)} weeks on hand (threshold: ${constraints.low_stock_weeks})`, confidence: "high" }
  }

  if (woh > constraints.overstock_weeks) {
    return { reason: "overstock", reasonText: `Overstock: ${woh.toFixed(1)} weeks on hand`, confidence: "medium" }
  }

  if (stats.trend_direction === "up" && stats.trend_percent_change > 15) {
    return { reason: "trending_up", reasonText: `Usage trending up ${stats.trend_percent_change.toFixed(0)}%`, confidence: "medium" }
  }

  if (woh < targetWeeks) {
    const hasIssues = stats.has_negative_usage || stats.has_gaps || stats.coefficient_of_variation > 1.0
    return { reason: "below_target", reasonText: `Below target: ${woh.toFixed(1)} weeks (target: ${targetWeeks})`, confidence: hasIssues ? "medium" : "high" }
  }

  if (stats.has_negative_usage || stats.has_gaps) {
    return { reason: "data_quality", reasonText: "Data quality issues - review manually", confidence: "low" }
  }

  return { reason: "below_target", reasonText: "Reorder suggested", confidence: "medium" }
}

function describeIssues(stats: ItemStats): string[] {
  const issues: string[] = []
  if (stats.has_negative_usage) issues.push("Negative usage detected (data entry error?)")
  if (stats.has_gaps) issues.push("Missing data periods")
  if (stats.coefficient_of_variation > 1.0) issues.push("High usage variability")
  return issues
}

export function generateRecommendations(
  items: Record<string, ParsedItem>,
  allStats: Record<string, ItemStats>,
  datasetId: string,
  request?: RecommendRequest,
): RecommendationRun {
  const targets = request?.targets ?? DEFAULT_TARGETS
  const constraints = request?.constraints ?? DEFAULT_CONSTRAINTS
  const forecast = request?.forecast

  const recommendations: Recommendation[] = []
  const warnings: string[] = []
  const dataIssues: { item_id: string; item_name: string; issues: string[] }[] = []

  for (const [itemId, stats] of Object.entries(allStats)) {
    const item = items[itemId]
    if (!item) continue

    // Apply filters
    if (request?.categories && item.category && !request.categories.includes(item.category)) continue
    if (request?.vendors && item.vendor && !request.vendors.includes(item.vendor)) continue
    if (request?.exclude_items?.includes(itemId)) continue
    if (targets.exclude_items.includes(itemId)) continue

    const targetWeeks = getTarget(targets, itemId, item.category)
    if (targetWeeks <= 0) continue
    if (stats.avg_usage <= 0) continue

    const woh = stats.weeks_on_hand ?? 0
    const { reason, reasonText, confidence } = determineReason(stats, targetWeeks, constraints)

    if (reason === "overstock") continue
    if (woh >= targetWeeks) continue

    const weeksNeeded = targetWeeks - woh
    let suggestedQty = Math.max(1, Math.round(weeksNeeded * stats.avg_usage))
    const baseSuggestedQty = suggestedQty
    let rt = reasonText

    // Trend adjustment
    if (stats.trend_direction === "up" && stats.trend_percent_change > 10) {
      suggestedQty = Math.round(suggestedQty * 1.1)
      rt += " (adjusted +10% for upward trend)"
    } else if (stats.trend_direction === "down" && stats.trend_percent_change < -10) {
      suggestedQty = Math.max(1, Math.round(suggestedQty * 0.9))
      rt += " (adjusted -10% for downward trend)"
    }

    // Forecast adjustment
    let forecastMultiplier: number | undefined
    const multiplier = getForecastMultiplier(forecast, item.category)
    if (multiplier !== 1.0) {
      forecastMultiplier = multiplier
      suggestedQty = Math.max(1, Math.round(suggestedQty * multiplier))
      const pctChange = (multiplier - 1.0) * 100
      if (Math.abs(pctChange) >= 5) {
        const dir = pctChange > 0 ? "increase" : "decrease"
        rt += ` (forecast: ${dir} ${Math.abs(pctChange).toFixed(0)}%)`
      }
    }

    const unitCost = item.unit_cost
    const totalCost = unitCost ? unitCost * suggestedQty : undefined

    recommendations.push({
      item_id: itemId,
      item_name: item.name,
      category: item.category,
      vendor: item.vendor,
      on_hand: stats.current_on_hand,
      avg_usage: stats.avg_usage,
      weeks_on_hand: woh,
      suggested_qty: suggestedQty,
      unit_cost: unitCost,
      total_cost: totalCost,
      reason,
      reason_text: rt,
      confidence,
      trend_direction: stats.trend_direction,
      trend_pct: stats.trend_percent_change,
      forecast_multiplier: forecastMultiplier,
      base_suggested_qty: forecastMultiplier ? baseSuggestedQty : undefined,
      warnings: stats.has_negative_usage || stats.has_gaps ? describeIssues(stats) : [],
    })

    if (stats.has_negative_usage || stats.has_gaps) {
      dataIssues.push({ item_id: itemId, item_name: item.name, issues: describeIssues(stats) })
    }
  }

  // Apply constraints
  let filtered = [...recommendations]
  if (constraints.max_items && filtered.length > constraints.max_items) {
    filtered = filtered.slice(0, constraints.max_items)
  }
  if (constraints.max_spend) {
    let total = 0
    filtered = filtered.filter((r) => {
      const cost = r.total_cost ?? 0
      if (total + cost <= constraints.max_spend!) {
        total += cost
        return true
      }
      return false
    })
  }

  // Sort by priority
  filtered.sort((a, b) => {
    const ap = a.reason === "stockout_risk" ? 0 : 1
    const bp = b.reason === "stockout_risk" ? 0 : 1
    if (ap !== bp) return ap - bp
    return (a.weeks_on_hand ?? 999) - (b.weeks_on_hand ?? 999)
  })

  // Build summary
  const totalSpend = filtered.reduce((s, r) => s + (r.total_cost ?? 0), 0)
  const byVendor: Record<string, { items: number; spend: number }> = {}
  const byCategory: Record<string, { items: number; spend: number }> = {}
  const byReason: Record<string, number> = {}

  for (const rec of filtered) {
    const v = rec.vendor || "Unknown"
    byVendor[v] = byVendor[v] ?? { items: 0, spend: 0 }
    byVendor[v].items++
    byVendor[v].spend += rec.total_cost ?? 0

    const c = rec.category || "Uncategorized"
    byCategory[c] = byCategory[c] ?? { items: 0, spend: 0 }
    byCategory[c].items++
    byCategory[c].spend += rec.total_cost ?? 0

    byReason[rec.reason] = (byReason[rec.reason] ?? 0) + 1
  }

  return {
    run_id: generateId("run"),
    dataset_id: datasetId,
    created_at: new Date().toISOString(),
    targets,
    constraints,
    forecast,
    recommendations: filtered,
    total_items: filtered.length,
    total_spend: totalSpend,
    low_stock_count: filtered.filter((r) => r.reason === "stockout_risk" || r.reason === "low_stock").length,
    overstock_count: 0,
    by_vendor: byVendor,
    by_category: byCategory,
    by_reason: byReason,
    warnings,
    data_issues: dataIssues,
    status: "completed",
  }
}
