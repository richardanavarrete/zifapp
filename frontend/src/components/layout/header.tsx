"use client"

import * as React from "react"
import { Moon, Sun, Monitor, LogOut } from "lucide-react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { useAppStore } from "@/store/app"
import { api } from "@/lib/api"

export function Header({ title }: { title?: string }) {
  const router = useRouter()
  const { theme, setTheme, profile, isGuest, logout } = useAppStore()

  const cycleTheme = () => {
    const themes: Array<"light" | "dark" | "system"> = ["light", "dark", "system"]
    const currentIndex = themes.indexOf(theme)
    const nextIndex = (currentIndex + 1) % themes.length
    setTheme(themes[nextIndex])
  }

  const handleLogout = async () => {
    if (!isGuest) {
      await api.logout()
    } else {
      logout()
    }
    router.replace("/login")
  }

  const ThemeIcon = theme === "dark" ? Moon : theme === "light" ? Sun : Monitor

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b bg-background/80 px-4 backdrop-blur-md lg:px-8">
      <div className="flex items-center gap-4">
        <div className="lg:hidden w-10" /> {/* Spacer for mobile menu button */}
        {title && <h1 className="text-xl font-semibold tracking-tight">{title}</h1>}
      </div>

      <div className="flex items-center gap-2">
        {(profile || isGuest) && (
          <span className="hidden text-sm text-muted-foreground sm:inline">
            {isGuest ? "Guest" : (profile?.full_name || profile?.email)}
          </span>
        )}
        <Button variant="ghost" size="icon" onClick={cycleTheme}>
          <ThemeIcon className="h-5 w-5" />
          <span className="sr-only">Toggle theme</span>
        </Button>
        <Button variant="ghost" size="icon" onClick={handleLogout}>
          <LogOut className="h-5 w-5" />
          <span className="sr-only">Sign out</span>
        </Button>
      </div>
    </header>
  )
}
