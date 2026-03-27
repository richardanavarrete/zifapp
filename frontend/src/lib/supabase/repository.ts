/**
 * Supabase Repository
 *
 * Database operations scoped by org_id for multi-tenancy.
 * Port of api/supabase/repository.py
 */

import type { SupabaseClient } from "@supabase/supabase-js"
import { getSupabaseAdminClient } from "./server"
import type { ParsedDataset, ParsedItem, ParsedRecord } from "../services/parser-service"

export class SupabaseRepository {
  private client: SupabaseClient
  private orgId: string

  constructor(orgId: string) {
    this.orgId = orgId
    this.client = getSupabaseAdminClient()
  }

  // =========================================================================
  // Dataset Operations
  // =========================================================================

  async saveDataset(dataset: ParsedDataset): Promise<void> {
    const now = new Date().toISOString()

    // Upsert dataset
    await this.client
      .from("datasets")
      .upsert(
        {
          dataset_id: dataset.dataset_id,
          org_id: this.orgId,
          name: dataset.name,
          created_at: dataset.created_at || now,
          updated_at: now,
          source_files: JSON.stringify(dataset.source_files),
          date_range_start: dataset.date_range_start ?? null,
          date_range_end: dataset.date_range_end ?? null,
          items_count: dataset.items_count,
          weeks_count: dataset.periods_count,
          metadata: "{}",
        },
        { onConflict: "dataset_id" },
      )
      .throwOnError()

    // Save items
    if (Object.keys(dataset.items).length > 0) {
      await this.client
        .from("items")
        .delete()
        .eq("dataset_id", dataset.dataset_id)
        .eq("org_id", this.orgId)

      const itemsData = Object.entries(dataset.items).map(([itemId, item]) => ({
        item_id: itemId,
        dataset_id: dataset.dataset_id,
        org_id: this.orgId,
        display_name: item.name,
        category: item.category ?? null,
        vendor: item.vendor ?? null,
        location: item.location ?? null,
        unit_cost: item.unit_cost ?? 0,
        unit_of_measure: item.unit_of_measure || "unit",
        metadata: "{}",
      }))

      // Batch insert in chunks of 500
      for (let i = 0; i < itemsData.length; i += 500) {
        await this.client.from("items").insert(itemsData.slice(i, i + 500)).throwOnError()
      }
    }

    // Save records
    if (dataset.records.length > 0) {
      await this.client
        .from("weekly_records")
        .delete()
        .eq("dataset_id", dataset.dataset_id)
        .eq("org_id", this.orgId)

      const recordsData = dataset.records.map((r) => ({
        item_id: r.item_id,
        dataset_id: dataset.dataset_id,
        org_id: this.orgId,
        week_date: r.record_date,
        on_hand: r.on_hand,
        usage: r.usage ?? 0,
        week_name: r.period_name ?? null,
        source_file: r.source_file ?? null,
      }))

      for (let i = 0; i < recordsData.length; i += 1000) {
        await this.client.from("weekly_records").insert(recordsData.slice(i, i + 1000)).throwOnError()
      }
    }
  }

  async getDataset(datasetId: string): Promise<ParsedDataset | null> {
    const { data: row } = await this.client
      .from("datasets")
      .select("*")
      .eq("dataset_id", datasetId)
      .eq("org_id", this.orgId)
      .maybeSingle()

    if (!row) return null

    // Get items
    const { data: itemRows } = await this.client
      .from("items")
      .select("*")
      .eq("dataset_id", datasetId)
      .eq("org_id", this.orgId)

    const items: Record<string, ParsedItem> = {}
    for (const ir of itemRows ?? []) {
      items[ir.item_id] = {
        item_id: ir.item_id,
        name: ir.display_name,
        category: ir.category,
        vendor: ir.vendor,
        location: ir.location,
        unit_cost: ir.unit_cost,
        unit_of_measure: ir.unit_of_measure,
      }
    }

    // Get records
    const { data: recRows } = await this.client
      .from("weekly_records")
      .select("*")
      .eq("dataset_id", datasetId)
      .eq("org_id", this.orgId)
      .order("week_date")

    const records: ParsedRecord[] = (recRows ?? []).map((r) => ({
      record_id: String(r.id),
      item_id: r.item_id,
      record_date: r.week_date,
      on_hand: r.on_hand,
      usage: r.usage,
      period_name: r.week_name,
      source_file: r.source_file,
    }))

    const sourceFiles = typeof row.source_files === "string" ? JSON.parse(row.source_files) : row.source_files ?? []

    return {
      dataset_id: row.dataset_id,
      name: row.name,
      created_at: row.created_at,
      source_files: sourceFiles,
      date_range_start: row.date_range_start,
      date_range_end: row.date_range_end,
      items_count: row.items_count,
      records_count: records.length,
      periods_count: row.weeks_count ?? 0,
      categories: [...new Set(Object.values(items).map((i) => i.category).filter(Boolean))] as string[],
      vendors: [...new Set(Object.values(items).map((i) => i.vendor).filter(Boolean))] as string[],
      items,
      records,
    }
  }

  async listDatasets(): Promise<
    {
      dataset_id: string
      name: string
      created_at: string
      items_count: number
      records_count: number
      periods_count: number
      date_range_start?: string
      date_range_end?: string
      categories: string[]
      vendors: string[]
    }[]
  > {
    const { data: rows } = await this.client
      .from("datasets")
      .select("*")
      .eq("org_id", this.orgId)
      .order("created_at", { ascending: false })

    return (rows ?? []).map((row) => ({
      dataset_id: row.dataset_id,
      name: row.name,
      created_at: row.created_at,
      items_count: row.items_count,
      records_count: 0,
      periods_count: row.weeks_count ?? 0,
      date_range_start: row.date_range_start,
      date_range_end: row.date_range_end,
      categories: [],
      vendors: [],
    }))
  }

  async deleteDataset(datasetId: string): Promise<boolean> {
    const { data } = await this.client
      .from("datasets")
      .select("dataset_id")
      .eq("dataset_id", datasetId)
      .eq("org_id", this.orgId)
      .maybeSingle()

    if (!data) return false

    // Delete in order
    await this.client.from("weekly_records").delete().eq("dataset_id", datasetId).eq("org_id", this.orgId)
    await this.client.from("items").delete().eq("dataset_id", datasetId).eq("org_id", this.orgId)

    const { data: runs } = await this.client.from("agent_runs").select("run_id").eq("dataset_id", datasetId).eq("org_id", this.orgId)
    for (const run of runs ?? []) {
      await this.client.from("agent_recommendations").delete().eq("run_id", run.run_id)
    }
    await this.client.from("agent_runs").delete().eq("dataset_id", datasetId).eq("org_id", this.orgId)
    await this.client.from("datasets").delete().eq("dataset_id", datasetId).eq("org_id", this.orgId)

    return true
  }

  // =========================================================================
  // Voice Session Operations
  // =========================================================================

  async saveVoiceSession(sessionData: Record<string, unknown>): Promise<void> {
    await this.client
      .from("voice_sessions")
      .upsert({ ...sessionData, org_id: this.orgId }, { onConflict: "session_id" })
      .throwOnError()
  }

  async getVoiceSessions(): Promise<Record<string, unknown>[]> {
    const { data } = await this.client
      .from("voice_sessions")
      .select("*")
      .eq("org_id", this.orgId)
      .order("created_at", { ascending: false })
    return data ?? []
  }

  async getVoiceSession(sessionId: string): Promise<Record<string, unknown> | null> {
    const { data } = await this.client
      .from("voice_sessions")
      .select("*")
      .eq("session_id", sessionId)
      .eq("org_id", this.orgId)
      .maybeSingle()
    return data
  }

  async saveVoiceRecord(recordData: Record<string, unknown>): Promise<void> {
    await this.client.from("voice_count_records").insert({ ...recordData, org_id: this.orgId }).throwOnError()
  }

  async getVoiceRecords(sessionId: string): Promise<Record<string, unknown>[]> {
    const { data } = await this.client
      .from("voice_count_records")
      .select("*")
      .eq("session_id", sessionId)
      .eq("org_id", this.orgId)
      .order("created_at")
    return data ?? []
  }

  // =========================================================================
  // Agent Run Operations
  // =========================================================================

  async saveAgentRun(run: Record<string, unknown>): Promise<void> {
    await this.client
      .from("agent_runs")
      .upsert({ ...run, org_id: this.orgId }, { onConflict: "run_id" })
      .throwOnError()
  }

  async getAgentRuns(datasetId?: string): Promise<Record<string, unknown>[]> {
    let query = this.client
      .from("agent_runs")
      .select("*")
      .eq("org_id", this.orgId)
      .order("created_at", { ascending: false })

    if (datasetId) query = query.eq("dataset_id", datasetId)

    const { data } = await query
    return data ?? []
  }

  async getAgentRun(runId: string): Promise<Record<string, unknown> | null> {
    const { data } = await this.client
      .from("agent_runs")
      .select("*")
      .eq("run_id", runId)
      .eq("org_id", this.orgId)
      .maybeSingle()
    return data
  }
}
