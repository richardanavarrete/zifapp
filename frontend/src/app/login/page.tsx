"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { api, ApiError } from "@/lib/api"
import { useAppStore } from "@/store/app"
type Mode = "login" | "register"

export default function LoginPage() {
  const router = useRouter()
  const { isAuthenticated, setAuth, setGuest } = useAppStore()
  const [mode, setMode] = React.useState<Mode>("login")
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const [email, setEmail] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [fullName, setFullName] = React.useState("")
  const [orgName, setOrgName] = React.useState("")
  const [inviteCode, setInviteCode] = React.useState("")

  React.useEffect(() => {
    if (isAuthenticated) {
      router.replace("/")
    }
  }, [isAuthenticated, router])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      let response
      if (mode === "login") {
        response = await api.login(email, password)
      } else {
        response = await api.register({
          email,
          password,
          full_name: fullName || undefined,
          organization_name: orgName || undefined,
          invite_code: inviteCode || undefined,
        })
      }
      setAuth(response)
      router.replace("/")
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError("Something went wrong. Please try again.")
      }
    } finally {
      setLoading(false)
    }
  }

  const switchMode = () => {
    setMode(mode === "login" ? "register" : "login")
    setError(null)
  }

  const handleGuestAccess = () => {
    setGuest()
    router.replace("/upload")
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <h1 className="text-3xl font-bold tracking-tight">Zif</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Smart inventory management
          </p>
        </div>

        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-center text-lg">
              {mode === "login" ? "Sign in" : "Create account"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              {mode === "register" && (
                <div className="space-y-1.5">
                  <label htmlFor="fullName" className="text-sm font-medium">
                    Full name
                  </label>
                  <Input
                    id="fullName"
                    type="text"
                    placeholder="Jane Smith"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    disabled={loading}
                  />
                </div>
              )}

              <div className="space-y-1.5">
                <label htmlFor="email" className="text-sm font-medium">
                  Email
                </label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  disabled={loading}
                  autoComplete="email"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="password" className="text-sm font-medium">
                  Password
                </label>
                <Input
                  id="password"
                  type="password"
                  placeholder={mode === "register" ? "Min 8 characters" : ""}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={mode === "register" ? 8 : undefined}
                  disabled={loading}
                  autoComplete={mode === "login" ? "current-password" : "new-password"}
                />
              </div>

              {mode === "register" && (
                <>
                  <div className="space-y-1.5">
                    <label htmlFor="orgName" className="text-sm font-medium">
                      Organization name
                    </label>
                    <Input
                      id="orgName"
                      type="text"
                      placeholder="My Restaurant"
                      value={orgName}
                      onChange={(e) => setOrgName(e.target.value)}
                      disabled={loading}
                    />
                    <p className="text-xs text-muted-foreground">
                      Create a new org, or use an invite code below to join one.
                    </p>
                  </div>

                  <div className="space-y-1.5">
                    <label htmlFor="inviteCode" className="text-sm font-medium">
                      Invite code
                    </label>
                    <Input
                      id="inviteCode"
                      type="text"
                      placeholder="Optional"
                      value={inviteCode}
                      onChange={(e) => setInviteCode(e.target.value)}
                      disabled={loading || !!orgName}
                    />
                  </div>
                </>
              )}

              <Button type="submit" className="w-full" disabled={loading}>
                {loading
                  ? mode === "login"
                    ? "Signing in..."
                    : "Creating account..."
                  : mode === "login"
                  ? "Sign in"
                  : "Create account"}
              </Button>
            </form>

            <div className="mt-4 text-center text-sm text-muted-foreground">
              {mode === "login" ? (
                <>
                  Don&apos;t have an account?{" "}
                  <button
                    type="button"
                    onClick={switchMode}
                    className="text-primary hover:underline"
                  >
                    Sign up
                  </button>
                </>
              ) : (
                <>
                  Already have an account?{" "}
                  <button
                    type="button"
                    onClick={switchMode}
                    className="text-primary hover:underline"
                  >
                    Sign in
                  </button>
                </>
              )}
            </div>

            <div className="relative mt-6">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-card px-2 text-muted-foreground">or</span>
              </div>
            </div>

            <div className="mt-4">
              <Button
                type="button"
                variant="outline"
                className="w-full"
                onClick={handleGuestAccess}
              >
                Continue as Guest
              </Button>
              <p className="mt-2 text-center text-xs text-muted-foreground">
                Upload and analyze a spreadsheet without an account.
                Data won&apos;t be saved between sessions.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
