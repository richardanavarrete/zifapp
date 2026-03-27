/**
 * Shared utilities for Next.js API route handlers.
 */

import { NextResponse } from "next/server"
import { extractToken, getUserFromToken, getUserOrgId } from "./supabase/server"

export function errorResponse(code: string, message: string, status = 400) {
  return NextResponse.json(
    { detail: { error: { code, message } } },
    { status },
  )
}

export function jsonResponse(data: unknown, status = 200) {
  return NextResponse.json(data, { status })
}

export interface AuthContext {
  userId: string
  email: string
  orgId: string | null
}

/**
 * Authenticate request and return user context.
 * Returns null + error response if not authenticated.
 */
export async function authenticate(
  request: Request,
): Promise<{ ctx: AuthContext } | { error: NextResponse }> {
  const token = extractToken(request)
  if (!token) {
    return { error: errorResponse("UNAUTHORIZED", "Missing authorization token", 401) }
  }

  const user = await getUserFromToken(token)
  if (!user) {
    return { error: errorResponse("UNAUTHORIZED", "Invalid or expired token", 401) }
  }

  const orgId = await getUserOrgId(user.id)

  return {
    ctx: {
      userId: user.id,
      email: user.email!,
      orgId,
    },
  }
}

/**
 * Optionally authenticate - returns null ctx if no token present.
 */
export async function authenticateOptional(
  request: Request,
): Promise<AuthContext | null> {
  const token = extractToken(request)
  if (!token) return null

  const user = await getUserFromToken(token)
  if (!user) return null

  const orgId = await getUserOrgId(user.id)

  return {
    userId: user.id,
    email: user.email!,
    orgId,
  }
}
