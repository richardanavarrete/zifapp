// API Types matching the FastAPI backend models

// ============== Inventory Models ==============

export interface Item {
  item_id: string
  name: string
  category?: string
  subcategory?: string
  vendor?: string
  sku?: string
  unit_cost?: number
  unit_of_measure?: string
  location?: string
  custom_fields: Record<string, unknown>
}

export interface InventoryRecord {
  record_id: string
  item_id: string
  record_date: string
  on_hand: number
  usage: number
  period_name?: string
  source_file?: string
  custom_fields: Record<string, unknown>
}

export interface ItemStats {
  current_on_hand: number
  total_usage: number
  avg_usage: number
  min_usage: number
  max_usage: number
  weeks_on_hand: number
  days_on_hand: number
  trend_direction: "up" | "down" | "stable"
  trend_percent_change: number
  std_deviation: number
  coefficient_of_variation: number
  record_count: number
  has_negative_usage: boolean
  has_gaps: boolean
}

export interface UsageTrend {
  period: string
  usage: number
  on_hand: number
}

export interface ItemDetail {
  item: Item
  stats: ItemStats
  history: UsageTrend[]
  rolling_avg_4wk: number[]
}

export interface Dataset {
  dataset_id: string
  name: string
  created_at: string
  updated_at: string
  source_files: string[]
  date_range_start?: string
  date_range_end?: string
  items_count: number
  records_count: number
  periods_count: number
  categories: string[]
  vendors: string[]
}

export interface DashboardData {
  dataset_id: string
  total_items: number
  total_on_hand: number
  total_usage: number
  periods_count: number
  date_range_start?: string
  date_range_end?: string
  categories: Record<string, { items: number; on_hand: number; usage: number }>
  alerts: Alert[]
  low_stock_items: ItemWithStats[]
  trending_up: ItemWithStats[]
  trending_down: ItemWithStats[]
}

export interface Alert {
  type: "low_stock" | "out_of_stock" | "trending_up" | "trending_down" | "data_issue"
  severity: "critical" | "warning" | "info"
  title: string
  message: string
  item_id?: string
  item_name?: string
}

export interface ItemWithStats extends Item {
  stats: ItemStats
}

export interface UploadResult {
  success: boolean
  dataset_id: string
  filename: string
  items_count: number
  records_count: number
  periods_count: number
  categories_found: string[]
  warnings: string[]
}

// ============== Voice Models ==============

export type SessionStatus = "in_progress" | "completed" | "cancelled"

export interface VoiceSession {
  session_id: string
  name: string
  created_at: string
  updated_at: string
  status: SessionStatus
  dataset_id?: string
  location?: string
  notes?: string
  items_counted: number
  total_units: number
}

export interface CountRecord {
  record_id: string
  session_id: string
  created_at: string
  raw_text: string
  item_id?: string
  item_name?: string
  quantity: number
  unit?: string
  match_confidence: number
  match_method: "exact" | "fuzzy" | "manual"
  confirmed: boolean
  manually_edited: boolean
}

export interface TranscriptionResult {
  transcription_id: string
  text: string
  duration_seconds: number
  confidence: number
  language: string
  chunks_processed: number
  processing_time_ms: number
  warnings: string[]
}

export interface MatchCandidate {
  item_id: string
  item_name: string
  score: number
  match_type: "exact" | "fuzzy"
}

export interface ParsedVoiceInput {
  raw_text: string
  quantity: number
  unit?: string
  item_text: string
  best_match?: MatchCandidate
  alternatives: MatchCandidate[]
  needs_review: boolean
  parse_confidence: number
}

export interface SessionExport {
  session_id: string
  session_name: string
  exported_at: string
  records: CountRecord[]
  total_items: number
  total_units: number
  by_category: Record<string, number>
  csv_text: string
  summary_text: string
}

// ============== Order Models ==============

export interface SalesForecast {
  percent_change?: number
  expected_total_sales?: number
  historical_avg_total_sales?: number
  by_category?: Record<string, number>
  historical_by_category?: Record<string, number>
  forecast_weeks?: number
  notes?: string
}

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

export type ReasonCode =
  | "stockout_risk"
  | "low_stock"
  | "trending_up"
  | "trending_down"
  | "restock"
  | "overstock"

export interface Recommendation {
  item_id: string
  item_name: string
  category?: string
  vendor?: string
  on_hand: number
  avg_usage: number
  weeks_on_hand: number
  suggested_qty: number
  unit_cost?: number
  total_cost: number
  reason: ReasonCode
  reason_text: string
  confidence: "high" | "medium" | "low"
  trend_direction: "up" | "down" | "stable"
  trend_pct: number
  forecast_multiplier: number
  base_suggested_qty: number
  warnings: string[]
}

export interface RecommendationRun {
  run_id: string
  dataset_id: string
  created_at: string
  targets: OrderTargets
  constraints?: OrderConstraints
  forecast?: SalesForecast
  recommendations: Recommendation[]
  total_items: number
  total_spend: number
  by_vendor: Record<string, { items: number; spend: number }>
  by_category: Record<string, { items: number; spend: number }>
  by_reason: Record<string, number>
  status: "completed" | "approved" | "exported"
}

export interface RecommendRequest {
  dataset_id: string
  targets?: OrderTargets
  constraints?: OrderConstraints
  forecast?: SalesForecast
  categories?: string[]
  vendors?: string[]
  exclude_items?: string[]
  include_overstock?: boolean
  min_confidence?: "high" | "medium" | "low"
}

// ============== API Response Wrappers ==============

export interface ApiResponse<T> {
  data?: T
  error?: ApiError
  request_id?: string
  timestamp?: string
}

export interface ApiError {
  code: string
  message: string
  details?: Record<string, unknown>
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  total_pages: number
}
