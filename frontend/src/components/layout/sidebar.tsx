"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard,
  Package,
  Mic,
  ShoppingCart,
  Settings,
  Upload,
  Menu,
  X,
  ChevronDown,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { useAppStore } from "@/store/app"

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Inventory", href: "/inventory", icon: Package },
  { name: "Voice Count", href: "/voice", icon: Mic },
  { name: "Orders", href: "/orders", icon: ShoppingCart },
  { name: "Upload", href: "/upload", icon: Upload },
  { name: "Settings", href: "/settings", icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()
  const { sidebarOpen, setSidebarOpen, activeDataset, isGuest, profile } = useAppStore()

  return (
    <>
      {/* Mobile menu button */}
      <Button
        variant="ghost"
        size="icon"
        className="fixed top-4 left-4 z-50 lg:hidden"
        onClick={() => setSidebarOpen(!sidebarOpen)}
      >
        {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </Button>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed left-0 top-0 z-40 h-screen w-64 transform border-r bg-card transition-transform duration-300 ease-in-out lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-full flex-col">
          {/* Logo */}
          <div className="flex h-16 items-center gap-3 border-b px-6">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground font-bold text-sm shadow-sm">
              Z
            </div>
            <span className="text-lg font-semibold tracking-tight">Zif</span>
          </div>

          {/* Dataset selector */}
          {activeDataset && (
            <div className="border-b px-4 py-3">
              <button className="flex w-full items-center justify-between rounded-md bg-muted px-3 py-2 text-sm hover:bg-muted/80">
                <div className="flex flex-col items-start">
                  <span className="text-xs text-muted-foreground">Dataset</span>
                  <span className="font-medium truncate max-w-[160px]">
                    {activeDataset.name}
                  </span>
                </div>
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              </button>
            </div>
          )}

          {/* Navigation */}
          <nav className="flex-1 space-y-1 px-3 py-4">
            {navigation.map((item) => {
              const isActive =
                item.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(item.href)

              return (
                <Link
                  key={item.name}
                  href={item.href}
                  onClick={() => setSidebarOpen(false)}
                  className={cn(
                    "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200",
                    isActive
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  )}
                >
                  {isActive && (
                    <span className="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-primary" />
                  )}
                  <item.icon className={cn("h-5 w-5 transition-colors", isActive ? "text-primary" : "group-hover:text-foreground")} />
                  {item.name}
                </Link>
              )
            })}
          </nav>

          {/* Footer */}
          <div className="border-t px-4 py-4">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-muted text-sm font-medium">
                {isGuest ? "G" : (profile?.full_name?.charAt(0) || profile?.email?.charAt(0) || "U").toUpperCase()}
              </div>
              <div className="flex-1 truncate">
                <p className="text-sm font-medium">{isGuest ? "Guest" : (profile?.full_name || profile?.email || "User")}</p>
                <p className="text-xs text-muted-foreground">{isGuest ? "Data not saved" : "Bar Manager"}</p>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </>
  )
}
