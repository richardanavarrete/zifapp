/**
 * Stats Service - Computes usage statistics and trends
 *
 * Port of smallcogs/services/stats_service.py
 */

import type { ParsedItem, ParsedRecord } from "./parser-service"

export interface ItemStats {
  item_id: string
  item_name: string
  category?: string
  current_on_hand: number
  last_count_date?: string
  total_usage: number
  avg_usage: number
  avg_usage_recent: number
  min_usage: number
  max_usage: number
  weeks_on_hand: number | null
  days_on_hand: number | null
  trend_direction: "up" | "down" | "stable"
  trend_percent_change: number
  std_deviation: number
  coefficient_of_variation: number
  record_count: number
  has_negative_usage: boolean
  has_gaps: boolean
}

export interface UsageTrend {
  date: string
  usage: number
  on_hand: number
  period_name?: string
}

export interface ItemDetail {
  item: ParsedItem
  stats: ItemStats
  history: UsageTrend[]
  rolling_avg_4wk: number[]
}

function mean(values: number[]): number {
  if (values.length === 0) return 0
  return values.reduce((a, b) => a + b, 0) / values.length
}

function stdev(values: number[]): number {
  if (values.length < 2) return 0
  const avg = mean(values)
  const variance = values.reduce((sum, v) => sum + (v - avg) ** 2, 0) / (values.length - 1)
  return Math.sqrt(variance)
}

function round(value: number, decimals: number): number {
  const factor = 10 ** decimals
  return Math.round(value * factor) / factor
}

export function computeItemStats(
  item: ParsedItem,
  records: ParsedRecord[],
  recentPeriods = 4,
): ItemStats {
  const sorted = [...records].sort((a, b) => a.record_date.localeCompare(b.record_date))

  if (sorted.length === 0) {
    return {
      item_id: item.item_id,
      item_name: item.name,
      category: item.category,
      current_on_hand: 0,
      total_usage: 0,
      avg_usage: 0,
      avg_usage_recent: 0,
      min_usage: 0,
      max_usage: 0,
      weeks_on_hand: null,
      days_on_hand: null,
      trend_direction: "stable",
      trend_percent_change: 0,
      std_deviation: 0,
      coefficient_of_variation: 0,
      record_count: 0,
      has_negative_usage: false,
      has_gaps: false,
    }
  }

  const usages = sorted.map((r) => r.usage).filter((u): u is number => u != null)
  const currentOnHand = sorted[sorted.length - 1].on_hand
  const lastCountDate = sorted[sorted.length - 1].record_date

  const totalUsage = usages.reduce((a, b) => a + b, 0)
  const avgUsage = mean(usages)
  const minUsage = usages.length > 0 ? Math.min(...usages) : 0
  const maxUsage = usages.length > 0 ? Math.max(...usages) : 0

  const recentUsages = usages.length >= recentPeriods ? usages.slice(-recentPeriods) : usages
  const avgUsageRecent = mean(recentUsages)

  let weeksOnHand: number | null = null
  let daysOnHand: number | null = null
  if (avgUsage > 0) {
    weeksOnHand = round(currentOnHand / avgUsage, 1)
    daysOnHand = round(currentOnHand / (avgUsage / 7), 1)
  }

  const [trendDirection, trendChange] = computeTrend(usages, recentPeriods)
  const stdDev = stdev(usages)
  const cv = avgUsage > 0 ? stdDev / avgUsage : 0

  const hasNegative = usages.some((u) => u < 0)
  const hasGaps = checkGaps(sorted)

  return {
    item_id: item.item_id,
    item_name: item.name,
    category: item.category,
    current_on_hand: currentOnHand,
    last_count_date: lastCountDate,
    total_usage: totalUsage,
    avg_usage: round(avgUsage, 2),
    avg_usage_recent: round(avgUsageRecent, 2),
    min_usage: minUsage,
    max_usage: maxUsage,
    weeks_on_hand: weeksOnHand,
    days_on_hand: daysOnHand,
    trend_direction: trendDirection,
    trend_percent_change: round(trendChange, 1),
    std_deviation: round(stdDev, 2),
    coefficient_of_variation: round(cv, 2),
    record_count: sorted.length,
    has_negative_usage: hasNegative,
    has_gaps: hasGaps,
  }
}

export function computeAllStats(
  items: Record<string, ParsedItem>,
  records: ParsedRecord[],
  recentPeriods = 4,
): Record<string, ItemStats> {
  const stats: Record<string, ItemStats> = {}
  for (const [itemId, item] of Object.entries(items)) {
    const itemRecords = records.filter((r) => r.item_id === itemId)
    stats[itemId] = computeItemStats(item, itemRecords, recentPeriods)
  }
  return stats
}

export function getItemDetail(
  item: ParsedItem,
  records: ParsedRecord[],
  recentPeriods = 4,
): ItemDetail {
  const itemRecords = records.filter((r) => r.item_id === item.item_id)
  const stats = computeItemStats(item, itemRecords, recentPeriods)

  const sorted = [...itemRecords].sort((a, b) => a.record_date.localeCompare(b.record_date))
  const history: UsageTrend[] = sorted.map((r) => ({
    date: r.record_date,
    usage: r.usage ?? 0,
    on_hand: r.on_hand,
    period_name: r.period_name,
  }))

  const usages = sorted.map((r) => r.usage ?? 0)
  const rollingAvg4wk = rollingAverage(usages, 4)

  return { item, stats, history, rolling_avg_4wk: rollingAvg4wk }
}

export function getCategorySummary(
  allStats: Record<string, ItemStats>,
): Record<string, { category: string; items_count: number; total_on_hand: number; total_usage: number; avg_weeks_on_hand: number | null }> {
  const summary: Record<string, { category: string; items_count: number; total_on_hand: number; total_usage: number; woh_list: number[] }> = {}

  for (const stats of Object.values(allStats)) {
    const cat = stats.category || "Uncategorized"
    if (!summary[cat]) {
      summary[cat] = { category: cat, items_count: 0, total_on_hand: 0, total_usage: 0, woh_list: [] }
    }
    summary[cat].items_count++
    summary[cat].total_on_hand += stats.current_on_hand
    summary[cat].total_usage += stats.total_usage
    if (stats.weeks_on_hand != null) {
      summary[cat].woh_list.push(stats.weeks_on_hand)
    }
  }

  const result: Record<string, { category: string; items_count: number; total_on_hand: number; total_usage: number; avg_weeks_on_hand: number | null }> = {}
  for (const [cat, data] of Object.entries(summary)) {
    result[cat] = {
      category: cat,
      items_count: data.items_count,
      total_on_hand: data.total_on_hand,
      total_usage: data.total_usage,
      avg_weeks_on_hand: data.woh_list.length > 0 ? round(mean(data.woh_list), 1) : null,
    }
  }
  return result
}

function computeTrend(usages: number[], recentPeriods: number): ["up" | "down" | "stable", number] {
  if (usages.length < recentPeriods * 2) return ["stable", 0]

  const recent = usages.slice(-recentPeriods)
  const earlier = usages.slice(-(recentPeriods * 2), -recentPeriods)

  const recentAvg = mean(recent)
  const earlierAvg = mean(earlier)

  if (earlierAvg === 0) return ["stable", 0]

  const pctChange = ((recentAvg - earlierAvg) / earlierAvg) * 100

  if (pctChange > 10) return ["up", pctChange]
  if (pctChange < -10) return ["down", pctChange]
  return ["stable", pctChange]
}

function checkGaps(sorted: ParsedRecord[]): boolean {
  if (sorted.length < 2) return false
  for (let i = 1; i < sorted.length; i++) {
    const prev = new Date(sorted[i - 1].record_date)
    const curr = new Date(sorted[i].record_date)
    const gap = (curr.getTime() - prev.getTime()) / (1000 * 60 * 60 * 24)
    if (gap > 14) return true
  }
  return false
}

function rollingAverage(values: number[], window: number): number[] {
  if (values.length < window) return values

  return values.map((_, i) => {
    const start = Math.max(0, i - window + 1)
    const slice = values.slice(start, i + 1)
    return round(mean(slice), 2)
  })
}
