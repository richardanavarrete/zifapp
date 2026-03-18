"use client"

import * as React from "react"
import { usePathname, useRouter } from "next/navigation"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ToastProvider, Toaster } from "@/hooks/use-toast"
import { ThemeProvider } from "@/components/theme-provider"
import { useAppStore } from "@/store/app"

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000, // 1 minute
        retry: 1,
      },
    },
  })
}

let browserQueryClient: QueryClient | undefined = undefined

function getQueryClient() {
  if (typeof window === "undefined") {
    return makeQueryClient()
  } else {
    if (!browserQueryClient) browserQueryClient = makeQueryClient()
    return browserQueryClient
  }
}

const PUBLIC_PATHS = ["/login"]

function AuthGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const isAuthenticated = useAppStore((s) => s.isAuthenticated)
  const [hydrated, setHydrated] = React.useState(false)

  React.useEffect(() => {
    setHydrated(true)
  }, [])

  React.useEffect(() => {
    if (!hydrated) return
    const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p))

    if (!isAuthenticated && !isPublic) {
      router.replace("/login")
    }
  }, [hydrated, isAuthenticated, pathname, router])

  // Don't render anything until store is hydrated to avoid flash
  if (!hydrated) {
    return null
  }

  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p))
  if (!isAuthenticated && !isPublic) {
    return null
  }

  return <>{children}</>
}

export function Providers({ children }: { children: React.ReactNode }) {
  const queryClient = getQueryClient()

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <ToastProvider>
          <AuthGuard>
            {children}
          </AuthGuard>
          <Toaster />
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}
