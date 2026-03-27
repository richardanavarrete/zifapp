/**
 * Voice Counting Service
 *
 * Handles text parsing, item matching, and session management.
 * Port of smallcogs/services/voice_service.py
 *
 * Note: Audio transcription is handled directly via OpenAI API in the route handler.
 */

import Fuse from "fuse.js"
import type { ParsedItem } from "./parser-service"

export interface MatchCandidate {
  item_id: string
  item_name: string
  category?: string
  confidence: number
  match_method: "exact" | "fuzzy" | "partial"
}

export interface ParsedVoiceInput {
  raw_text: string
  quantity: number
  unit: string
  item_text: string | null
  best_match?: MatchCandidate
  alternatives: MatchCandidate[]
  needs_review: boolean
  parse_confidence: number
}

export interface VoiceMatchResponse {
  parsed_items: ParsedVoiceInput[]
  unmatched_text: string[]
  processing_time_ms: number
}

export function matchText(
  text: string,
  items: Record<string, ParsedItem>,
  confidenceThreshold = 0.7,
  maxAlternatives = 3,
): VoiceMatchResponse {
  const start = performance.now()

  const segments = splitSegments(text)
  const parsedItems: ParsedVoiceInput[] = []
  const unmatched: string[] = []

  for (const segment of segments) {
    const trimmed = segment.trim()
    if (!trimmed) continue

    const parsed = parseSegment(trimmed)

    if (parsed.item_text && Object.keys(items).length > 0) {
      const matches = findMatches(parsed.item_text, items, maxAlternatives + 1)

      if (matches.length > 0 && matches[0].confidence >= confidenceThreshold) {
        parsed.best_match = matches[0]
        parsed.alternatives = matches.slice(1, maxAlternatives + 1)
        parsed.parse_confidence = matches[0].confidence
      } else {
        parsed.needs_review = true
        parsed.alternatives = matches.slice(0, maxAlternatives)
      }
    } else {
      parsed.needs_review = true
    }

    if (parsed.item_text) {
      parsedItems.push(parsed)
    } else {
      unmatched.push(trimmed)
    }
  }

  return {
    parsed_items: parsedItems,
    unmatched_text: unmatched,
    processing_time_ms: performance.now() - start,
  }
}

function splitSegments(text: string): string[] {
  let t = text.replace(/\n/g, ",")
  t = t.replace(/\band\b/gi, ",")
  return t
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
}

function parseSegment(segment: string): ParsedVoiceInput {
  const lower = segment.toLowerCase().trim()

  // Patterns: "2 bottles of buffalo trace", "buffalo trace 2 bottles", "buffalo trace, 2"
  const patterns = [
    /^(\d+(?:\.\d+)?)\s*(bottles?|cases?|units?|each)?\s*(?:of\s+)?(.+)$/i,
    /^(.+?)\s+(\d+(?:\.\d+)?)\s*(bottles?|cases?|units?|each)?$/i,
    /^(.+?),?\s+(\d+(?:\.\d+)?)$/i,
  ]

  for (const pattern of patterns) {
    const match = lower.match(pattern)
    if (!match) continue
    const groups = match.slice(1)

    if (groups[0] && /^\d/.test(groups[0])) {
      const qty = parseFloat(groups[0])
      const unit = (groups[1] || "units").replace(/s$/, "")
      const item = groups[2]?.trim() || ""
      return {
        raw_text: segment,
        quantity: qty,
        unit,
        item_text: item || null,
        alternatives: [],
        needs_review: false,
        parse_confidence: 0,
      }
    } else {
      const item = groups[0]?.trim() || ""
      const qty = groups[1] ? parseFloat(groups[1]) : 1
      const unit = groups[2] ? groups[2].replace(/s$/, "") : "unit"
      return {
        raw_text: segment,
        quantity: qty,
        unit,
        item_text: item || null,
        alternatives: [],
        needs_review: false,
        parse_confidence: 0,
      }
    }
  }

  // No pattern matched
  return {
    raw_text: segment,
    quantity: 1,
    unit: "unit",
    item_text: lower,
    alternatives: [],
    needs_review: true,
    parse_confidence: 0,
  }
}

function findMatches(
  searchText: string,
  items: Record<string, ParsedItem>,
  maxResults: number,
): MatchCandidate[] {
  const itemList = Object.values(items)

  const fuse = new Fuse(itemList, {
    keys: ["name"],
    threshold: 0.6,
    includeScore: true,
    minMatchCharLength: 2,
  })

  const results = fuse.search(searchText, { limit: maxResults })

  return results.map((r) => ({
    item_id: r.item.item_id,
    item_name: r.item.name,
    category: r.item.category,
    confidence: 1 - (r.score ?? 1),
    match_method: (r.score ?? 1) === 0 ? ("exact" as const) : ("fuzzy" as const),
  }))
}
