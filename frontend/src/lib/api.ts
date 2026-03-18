import type {
  Dataset,
  DashboardData,
  Item,
  ItemDetail,
  UploadResult,
  VoiceSession,
  CountRecord,
  TranscriptionResult,
  ParsedVoiceInput,
  SessionExport,
  RecommendationRun,
  RecommendRequest,
  OrderTargets,
  OrderConstraints,
  LoginResponse,
  AuthTokens,
  ApiResponse,
} from "@/types/api"
import { useAppStore } from "@/store/app"

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
const API_PREFIX = "/api/v1"

class ApiClient {
  private baseUrl: string
  private apiKey?: string

  constructor() {
    this.baseUrl = `${API_BASE_URL}${API_PREFIX}`
    this.apiKey = process.env.NEXT_PUBLIC_API_KEY
  }

  private getAccessToken(): string | null {
    return useAppStore.getState().tokens?.access_token ?? null
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    }

    const token = this.getAccessToken()
    if (token) {
      headers["Authorization"] = `Bearer ${token}`
    }

    if (this.apiKey) {
      headers["X-API-Key"] = this.apiKey
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers,
    })

    if (response.status === 401) {
      // Try to refresh token
      const refreshed = await this.tryRefreshToken()
      if (refreshed) {
        // Retry with new token
        headers["Authorization"] = `Bearer ${this.getAccessToken()}`
        const retryResponse = await fetch(`${this.baseUrl}${endpoint}`, {
          ...options,
          headers,
        })
        if (retryResponse.ok) {
          return retryResponse.json()
        }
      }
      // Refresh failed - force logout
      useAppStore.getState().logout()
      throw new ApiError("AUTH_EXPIRED", "Session expired. Please log in again.", 401)
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new ApiError(
        error.error?.code || "UNKNOWN_ERROR",
        error.error?.message || `Request failed with status ${response.status}`,
        response.status
      )
    }

    return response.json()
  }

  private async upload<T>(
    endpoint: string,
    formData: FormData
  ): Promise<T> {
    const headers: Record<string, string> = {}

    const token = this.getAccessToken()
    if (token) {
      headers["Authorization"] = `Bearer ${token}`
    }

    if (this.apiKey) {
      headers["X-API-Key"] = this.apiKey
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: "POST",
      headers,
      body: formData,
    })

    if (response.status === 401) {
      const refreshed = await this.tryRefreshToken()
      if (refreshed) {
        headers["Authorization"] = `Bearer ${this.getAccessToken()}`
        const retryResponse = await fetch(`${this.baseUrl}${endpoint}`, {
          method: "POST",
          headers,
          body: formData,
        })
        if (retryResponse.ok) {
          return retryResponse.json()
        }
      }
      useAppStore.getState().logout()
      throw new ApiError("AUTH_EXPIRED", "Session expired. Please log in again.", 401)
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new ApiError(
        error.error?.code || "UPLOAD_ERROR",
        error.error?.message || `Upload failed with status ${response.status}`,
        response.status
      )
    }

    return response.json()
  }

  private async tryRefreshToken(): Promise<boolean> {
    const refreshToken = useAppStore.getState().tokens?.refresh_token
    if (!refreshToken) return false

    try {
      const response = await fetch(`${this.baseUrl}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
      if (!response.ok) return false

      const tokens: AuthTokens = await response.json()
      useAppStore.getState().updateTokens(tokens)
      return true
    } catch {
      return false
    }
  }

  // ============== Auth ==============

  async login(email: string, password: string): Promise<LoginResponse> {
    const response = await fetch(`${this.baseUrl}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new ApiError(
        error.detail?.error?.code || "LOGIN_FAILED",
        error.detail?.error?.message || "Invalid email or password",
        response.status
      )
    }

    return response.json()
  }

  async register(data: {
    email: string
    password: string
    full_name?: string
    organization_name?: string
    invite_code?: string
  }): Promise<LoginResponse> {
    const response = await fetch(`${this.baseUrl}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new ApiError(
        error.detail?.error?.code || "REGISTER_FAILED",
        error.detail?.error?.message || "Registration failed",
        response.status
      )
    }

    return response.json()
  }

  async logout(): Promise<void> {
    try {
      await this.request("/auth/logout", { method: "POST" })
    } catch {
      // Ignore errors on logout
    }
    useAppStore.getState().logout()
  }

  // ============== Health ==============

  async healthCheck(): Promise<{ status: string }> {
    return this.request("/health")
  }

  // ============== Inventory ==============

  async uploadInventory(
    file: File,
    options?: { skipRows?: number }
  ): Promise<UploadResult> {
    const formData = new FormData()
    formData.append("file", file)
    if (options?.skipRows) {
      formData.append("skip_rows", options.skipRows.toString())
    }
    return this.upload("/inventory/upload", formData)
  }

  async getDatasets(): Promise<Dataset[]> {
    return this.request("/inventory/datasets")
  }

  async getDataset(datasetId: string): Promise<Dataset> {
    return this.request(`/inventory/datasets/${datasetId}`)
  }

  async deleteDataset(datasetId: string): Promise<void> {
    return this.request(`/inventory/datasets/${datasetId}`, {
      method: "DELETE",
    })
  }

  async getItems(
    datasetId: string,
    params?: {
      search?: string
      category?: string
      vendor?: string
      sort_by?: string
      sort_order?: "asc" | "desc"
      page?: number
      per_page?: number
    }
  ): Promise<{ items: (Item & { stats: ItemDetail["stats"] })[]; total: number }> {
    const searchParams = new URLSearchParams()
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== "") {
          searchParams.append(key, String(value))
        }
      })
    }
    const query = searchParams.toString()
    return this.request(
      `/inventory/datasets/${datasetId}/items${query ? `?${query}` : ""}`
    )
  }

  async getItem(datasetId: string, itemId: string): Promise<ItemDetail> {
    return this.request(`/inventory/datasets/${datasetId}/items/${itemId}`)
  }

  async getDashboard(datasetId: string): Promise<DashboardData> {
    return this.request(`/inventory/datasets/${datasetId}/dashboard`)
  }

  // ============== Voice Counting ==============

  async createVoiceSession(data: {
    name: string
    dataset_id?: string
    location?: string
    notes?: string
  }): Promise<VoiceSession> {
    return this.request("/voice/sessions", {
      method: "POST",
      body: JSON.stringify(data),
    })
  }

  async getVoiceSessions(status?: string): Promise<VoiceSession[]> {
    const query = status ? `?status=${status}` : ""
    return this.request(`/voice/sessions${query}`)
  }

  async getVoiceSession(sessionId: string): Promise<VoiceSession> {
    return this.request(`/voice/sessions/${sessionId}`)
  }

  async completeVoiceSession(sessionId: string): Promise<VoiceSession> {
    return this.request(`/voice/sessions/${sessionId}/complete`, {
      method: "POST",
    })
  }

  async transcribeAudio(audioFile: File): Promise<TranscriptionResult> {
    const formData = new FormData()
    formData.append("file", audioFile)
    return this.upload("/voice/transcribe", formData)
  }

  async matchVoiceInput(data: {
    text: string
    dataset_id?: string
    session_id?: string
    confidence_threshold?: number
    max_alternatives?: number
  }): Promise<ParsedVoiceInput> {
    return this.request("/voice/match", {
      method: "POST",
      body: JSON.stringify(data),
    })
  }

  async addCountRecord(
    sessionId: string,
    data: {
      raw_text: string
      item_id?: string
      item_name?: string
      quantity: number
      unit?: string
      match_confidence?: number
      match_method?: "exact" | "fuzzy" | "manual"
    }
  ): Promise<CountRecord> {
    return this.request(`/voice/sessions/${sessionId}/records`, {
      method: "POST",
      body: JSON.stringify(data),
    })
  }

  async getCountRecords(sessionId: string): Promise<CountRecord[]> {
    return this.request(`/voice/sessions/${sessionId}/records`)
  }

  async confirmCountRecord(
    sessionId: string,
    recordId: string
  ): Promise<CountRecord> {
    return this.request(
      `/voice/sessions/${sessionId}/records/${recordId}/confirm`,
      { method: "POST" }
    )
  }

  async updateCountRecord(
    sessionId: string,
    recordId: string,
    data: Partial<CountRecord>
  ): Promise<CountRecord> {
    return this.request(`/voice/sessions/${sessionId}/records/${recordId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    })
  }

  async exportSession(
    sessionId: string,
    format: "csv" | "text" = "csv"
  ): Promise<SessionExport> {
    return this.request(`/voice/sessions/${sessionId}/export?format=${format}`)
  }

  // ============== Order Recommendations ==============

  async generateRecommendations(
    request: RecommendRequest
  ): Promise<RecommendationRun> {
    return this.request("/orders/recommend", {
      method: "POST",
      body: JSON.stringify(request),
    })
  }

  async getRecommendationRuns(): Promise<RecommendationRun[]> {
    return this.request("/orders/runs")
  }

  async getRecommendationRun(runId: string): Promise<RecommendationRun> {
    return this.request(`/orders/runs/${runId}`)
  }

  async approveRecommendations(
    runId: string,
    data: {
      approved_items?: string[]
      modified_quantities?: Record<string, number>
      rejected_items?: string[]
    }
  ): Promise<RecommendationRun> {
    return this.request(`/orders/runs/${runId}/approve`, {
      method: "POST",
      body: JSON.stringify(data),
    })
  }

  async exportRecommendations(
    runId: string,
    format: "csv" | "pdf" = "csv"
  ): Promise<Blob> {
    const headers: HeadersInit = {}

    const token = this.getAccessToken()
    if (token) {
      headers["Authorization"] = `Bearer ${token}`
    }
    if (this.apiKey) {
      headers["X-API-Key"] = this.apiKey
    }

    const response = await fetch(
      `${this.baseUrl}/orders/runs/${runId}/export?format=${format}`,
      { headers }
    )

    if (!response.ok) {
      throw new ApiError("EXPORT_ERROR", "Failed to export recommendations", response.status)
    }

    return response.blob()
  }

  async getDefaultTargets(): Promise<OrderTargets> {
    return this.request("/orders/targets/default")
  }

  async getDefaultConstraints(): Promise<OrderConstraints> {
    return this.request("/orders/constraints/default")
  }
}

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status?: number
  ) {
    super(message)
    this.name = "ApiError"
  }
}

export const api = new ApiClient()
