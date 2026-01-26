"use client"

import * as React from "react"
import { Moon, Sun, Monitor, Save } from "lucide-react"
import { PageLayout } from "@/components/layout/page-layout"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useToast } from "@/hooks/use-toast"
import { useAppStore } from "@/store/app"
import { cn } from "@/lib/utils"

function ThemeSelector() {
  const { theme, setTheme } = useAppStore()

  const themes = [
    { value: "light" as const, label: "Light", icon: Sun },
    { value: "dark" as const, label: "Dark", icon: Moon },
    { value: "system" as const, label: "System", icon: Monitor },
  ]

  return (
    <div className="grid grid-cols-3 gap-2">
      {themes.map(({ value, label, icon: Icon }) => (
        <button
          key={value}
          onClick={() => setTheme(value)}
          className={cn(
            "flex flex-col items-center gap-2 rounded-lg border p-4 transition-colors",
            theme === value
              ? "border-primary bg-primary/5"
              : "hover:bg-muted/50"
          )}
        >
          <Icon className="h-6 w-6" />
          <span className="text-sm font-medium">{label}</span>
        </button>
      ))}
    </div>
  )
}

function OrderTargetsSettings() {
  const { addToast } = useToast()
  const { orderTargets, setOrderTargets } = useAppStore()

  const [defaultWeeks, setDefaultWeeks] = React.useState(
    orderTargets.default_weeks.toString()
  )
  const [categoryTargets, setCategoryTargets] = React.useState<
    { category: string; weeks: string }[]
  >(
    (Object.entries(orderTargets.by_category) as [string, number][]).map(([category, weeks]) => ({
      category,
      weeks: weeks.toString(),
    }))
  )

  const handleSave = () => {
    const newTargets = {
      default_weeks: parseFloat(defaultWeeks) || 2,
      by_category: categoryTargets.reduce((acc, { category, weeks }) => {
        if (category && weeks) {
          acc[category] = parseFloat(weeks)
        }
        return acc
      }, {} as Record<string, number>),
    }
    setOrderTargets(newTargets)
    addToast({ title: "Settings saved", variant: "success" })
  }

  const addCategoryTarget = () => {
    setCategoryTargets([...categoryTargets, { category: "", weeks: "" }])
  }

  const removeCategoryTarget = (index: number) => {
    setCategoryTargets(categoryTargets.filter((_, i) => i !== index))
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <label className="text-sm font-medium">Default Weeks of Stock</label>
        <p className="text-xs text-muted-foreground">
          Target inventory level for all items
        </p>
        <Input
          type="number"
          value={defaultWeeks}
          onChange={(e) => setDefaultWeeks(e.target.value)}
          min={0.5}
          max={12}
          step={0.5}
          className="w-24"
        />
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium">Category-specific Targets</label>
        <p className="text-xs text-muted-foreground">
          Override default targets for specific categories
        </p>
        <div className="space-y-2">
          {categoryTargets.map((target, index) => (
            <div key={index} className="flex items-center gap-2">
              <Input
                placeholder="Category"
                value={target.category}
                onChange={(e) => {
                  const updated = [...categoryTargets]
                  updated[index].category = e.target.value
                  setCategoryTargets(updated)
                }}
                className="flex-1"
              />
              <Input
                type="number"
                placeholder="Weeks"
                value={target.weeks}
                onChange={(e) => {
                  const updated = [...categoryTargets]
                  updated[index].weeks = e.target.value
                  setCategoryTargets(updated)
                }}
                className="w-24"
              />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => removeCategoryTarget(index)}
              >
                Remove
              </Button>
            </div>
          ))}
          <Button variant="outline" size="sm" onClick={addCategoryTarget}>
            Add Category Target
          </Button>
        </div>
      </div>

      <Button onClick={handleSave}>
        <Save className="mr-2 h-4 w-4" />
        Save Targets
      </Button>
    </div>
  )
}

function OrderConstraintsSettings() {
  const { addToast } = useToast()
  const { orderConstraints, setOrderConstraints } = useAppStore()

  const [maxSpend, setMaxSpend] = React.useState(
    orderConstraints.max_spend?.toString() || ""
  )
  const [maxItems, setMaxItems] = React.useState(
    orderConstraints.max_items?.toString() || ""
  )
  const [lowStockWeeks, setLowStockWeeks] = React.useState(
    orderConstraints.low_stock_weeks.toString()
  )
  const [overstockWeeks, setOverstockWeeks] = React.useState(
    orderConstraints.overstock_weeks.toString()
  )

  const handleSave = () => {
    setOrderConstraints({
      max_spend: maxSpend ? parseFloat(maxSpend) : undefined,
      max_items: maxItems ? parseInt(maxItems) : undefined,
      low_stock_weeks: parseFloat(lowStockWeeks) || 1,
      overstock_weeks: parseFloat(overstockWeeks) || 6,
    })
    addToast({ title: "Settings saved", variant: "success" })
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <label className="text-sm font-medium">Max Budget</label>
          <p className="text-xs text-muted-foreground">
            Maximum spend per order (optional)
          </p>
          <Input
            type="number"
            value={maxSpend}
            onChange={(e) => setMaxSpend(e.target.value)}
            placeholder="No limit"
            min={0}
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">Max Items</label>
          <p className="text-xs text-muted-foreground">
            Maximum items per order (optional)
          </p>
          <Input
            type="number"
            value={maxItems}
            onChange={(e) => setMaxItems(e.target.value)}
            placeholder="No limit"
            min={0}
          />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <label className="text-sm font-medium">Low Stock Threshold</label>
          <p className="text-xs text-muted-foreground">
            Weeks on hand considered low
          </p>
          <Input
            type="number"
            value={lowStockWeeks}
            onChange={(e) => setLowStockWeeks(e.target.value)}
            min={0.5}
            max={4}
            step={0.5}
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">Overstock Threshold</label>
          <p className="text-xs text-muted-foreground">
            Weeks on hand considered overstock
          </p>
          <Input
            type="number"
            value={overstockWeeks}
            onChange={(e) => setOverstockWeeks(e.target.value)}
            min={2}
            max={12}
            step={0.5}
          />
        </div>
      </div>

      <Button onClick={handleSave}>
        <Save className="mr-2 h-4 w-4" />
        Save Constraints
      </Button>
    </div>
  )
}

function AccountSettings() {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted text-xl font-medium">
          JD
        </div>
        <div>
          <p className="font-medium">John Doe</p>
          <p className="text-sm text-muted-foreground">john@example.com</p>
          <p className="text-xs text-muted-foreground">Bar Manager</p>
        </div>
      </div>
      <p className="text-sm text-muted-foreground">
        Account management coming soon. Contact support for account changes.
      </p>
    </div>
  )
}

export default function SettingsPage() {
  return (
    <PageLayout title="Settings">
      <div className="space-y-6 max-w-2xl">
        {/* Appearance */}
        <Card>
          <CardHeader>
            <CardTitle>Appearance</CardTitle>
            <CardDescription>
              Customize how Zif looks on your device
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ThemeSelector />
          </CardContent>
        </Card>

        {/* Order Targets */}
        <Card>
          <CardHeader>
            <CardTitle>Order Targets</CardTitle>
            <CardDescription>
              Set default inventory targets for order recommendations
            </CardDescription>
          </CardHeader>
          <CardContent>
            <OrderTargetsSettings />
          </CardContent>
        </Card>

        {/* Order Constraints */}
        <Card>
          <CardHeader>
            <CardTitle>Order Constraints</CardTitle>
            <CardDescription>
              Set budget and quantity limits for orders
            </CardDescription>
          </CardHeader>
          <CardContent>
            <OrderConstraintsSettings />
          </CardContent>
        </Card>

        {/* Account */}
        <Card>
          <CardHeader>
            <CardTitle>Account</CardTitle>
            <CardDescription>Manage your account settings</CardDescription>
          </CardHeader>
          <CardContent>
            <AccountSettings />
          </CardContent>
        </Card>
      </div>
    </PageLayout>
  )
}
