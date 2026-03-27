import { NextRequest } from "next/server"
import OpenAI from "openai"
import { authenticate, errorResponse, jsonResponse } from "@/lib/api-utils"

function generateId(prefix: string): string {
  const hex = Array.from(crypto.getRandomValues(new Uint8Array(6)))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
  return `${prefix}_${hex}`
}

export async function POST(request: NextRequest) {
  const result = await authenticate(request)
  if ("error" in result) return result.error

  const apiKey = process.env.OPENAI_API_KEY
  if (!apiKey) {
    return errorResponse("CONFIG_ERROR", "OpenAI API key not configured", 500)
  }

  const formData = await request.formData()
  const audioFile = formData.get("file") as File | null
  const language = (formData.get("language") as string) || "en"

  if (!audioFile) return errorResponse("VALIDATION_ERROR", "No audio file provided")

  const start = performance.now()

  try {
    const openai = new OpenAI({ apiKey })

    const response = await openai.audio.transcriptions.create({
      model: "whisper-1",
      file: audioFile,
      language,
      response_format: "text",
    })

    const text = typeof response === "string" ? response.trim() : ""
    const processingTime = performance.now() - start

    return jsonResponse({
      transcription_id: generateId("tr"),
      text,
      duration_seconds: 0,
      confidence: 0.9,
      language,
      chunks_processed: 1,
      processing_time_ms: processingTime,
      warnings: [],
    })
  } catch (e) {
    console.error("Transcription error:", e)
    return errorResponse("TRANSCRIPTION_ERROR", e instanceof Error ? e.message : "Transcription failed", 500)
  }
}
