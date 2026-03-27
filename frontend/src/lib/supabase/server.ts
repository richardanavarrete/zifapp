/**
 * Server-side Supabase client for Next.js API routes.
 *
 * Uses the service role key for admin operations (bypasses RLS).
 */

import { createClient, SupabaseClient } from "@supabase/supabase-js"

let _client: SupabaseClient | null = null
let _adminClient: SupabaseClient | null = null

export function getSupabaseClient(): SupabaseClient {
  if (_client) return _client

  const url = process.env.SUPABASE_URL
  const anonKey = process.env.SUPABASE_ANON_KEY

  if (!url || !anonKey) {
    throw new Error("SUPABASE_URL and SUPABASE_ANON_KEY are required")
  }

  _client = createClient(url, anonKey)
  return _client
}

export function getSupabaseAdminClient(): SupabaseClient {
  if (_adminClient) return _adminClient

  const url = process.env.SUPABASE_URL
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY

  if (!url || !serviceRoleKey) {
    throw new Error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
  }

  _adminClient = createClient(url, serviceRoleKey)
  return _adminClient
}

/**
 * Get the user from a Bearer token by calling Supabase auth.getUser().
 */
export async function getUserFromToken(token: string) {
  const client = getSupabaseClient()
  const { data, error } = await client.auth.getUser(token)
  if (error || !data.user) return null
  return data.user
}

/**
 * Extract Bearer token from Authorization header.
 */
export function extractToken(request: Request): string | null {
  const auth = request.headers.get("authorization")
  if (!auth?.startsWith("Bearer ")) return null
  return auth.slice(7)
}

/**
 * Get the authenticated user's org_id from the organization_members table.
 */
export async function getUserOrgId(userId: string): Promise<string | null> {
  const admin = getSupabaseAdminClient()
  const { data } = await admin
    .from("organization_members")
    .select("org_id")
    .eq("user_id", userId)
    .maybeSingle()

  return data?.org_id ?? null
}
