"use client"

import * as React from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  ShoppingCart,
  Check,
  X,
  Download,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Package,
  TrendingUp,
  TrendingDown,
  Minus,
} from "lucide-react"
import Link from "next/link"
import { PageLayout } from "@/components/layout/page-layout"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { useToast } from "@/hooks/use-toast"
import { api } from "@/lib/api"
import { useAppStore } from "@/store/app"
import { cn, formatCurrency, formatNumber } from "@/lib/utils"
import type { RecommendationRun, Recommendation } from "@/types/api"

function TrendIcon({ direction }: { direction: string }) {
  if (direction === "up") return <TrendingUp className="h-4 w-4 text-success" />
  if (direction === "down") return <TrendingDown className="h-4 w-4 text-destructive" />
  return <Minus className="h-4 w-4 text-muted-foreground" />
}

function ReasonBadge({ reason }: { reason: string }) {
  const variants: Record<string, "destructive" | "warning" | "default" | "secondary"> = {
    stockout_risk: "destructive",
    low_stock: "warning",
    trending_up: "default",
    trending_down: "secondary",
    restock: "default",
    overstock: "secondary",
  }
  const labels: Record<string, string> = {
    stockout_risk: "Stockout Risk",
    low_stock: "Low Stock",
    trending_up: "Trending Up",
    trending_down: "Trending Down",
    restock: "Restock",
    overstock: "Overstock",
  }
  return (
    <Badge variant={variants[reason] || "secondary"}>
      {labels[reason] || reason}
    </Badge>
  )
}

function RecommendationCard({
  rec,
  selected,
  onToggle,
  onQuantityChange,
  customQuantity,
}: {
  rec: Recommendation
  selected: boolean
  onToggle: () => void
  onQuantityChange: (qty: number) => void
  customQuantity?: number
}) {
  const [expanded, setExpanded] = React.useState(false)
  const qty = customQuantity ?? rec.suggested_qty

  return (
    <div
      className={cn(
        "rounded-lg border p-4 transition-colors",
        selected ? "border-primary bg-primary/5" : "hover:bg-muted/50"
      )}
    >
      <div className="flex items-start gap-4">
        <button
          onClick={onToggle}
          className={cn(
            "flex h-6 w-6 items-center justify-center rounded-md border transition-colors",
            selected
              ? "bg-primary border-primary text-primary-foreground"
              : "border-input hover:bg-muted"
          )}
        >
          {selected && <Check className="h-4 w-4" />}
        </button>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-medium">{rec.item_name}</p>
            <ReasonBadge reason={rec.reason} />
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            {rec.category} {rec.vendor && `• ${rec.vendor}`}
          </p>

          <div className="flex items-center gap-4 mt-3">
            <div className="flex items-center gap-2">
              <label className="text-sm text-muted-foreground">Qty:</label>
              <Input
                type="number"
                value={qty}
                onChange={(e) => onQuantityChange(parseInt(e.target.value) || 0)}
                className="w-20 h-8"
                min={0}
              />
            </div>
            {rec.unit_cost && (
              <p className="text-sm">
                {formatCurrency(rec.unit_cost)} each ={" "}
                <span className="font-medium">
                  {formatCurrency(qty * rec.unit_cost)}
                </span>
              </p>
            )}
          </div>

          {expanded && (
            <div className="mt-4 pt-4 border-t space-y-2 text-sm">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-muted-foreground">Current On Hand</p>
                  <p className="font-medium">{formatNumber(rec.on_hand)}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Avg Weekly Usage</p>
                  <p className="font-medium">{formatNumber(rec.avg_usage)}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Weeks on Hand</p>
                  <p className="font-medium">{rec.weeks_on_hand.toFixed(1)}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Trend</p>
                  <div className="flex items-center gap-1">
                    <TrendIcon direction={rec.trend_direction} />
                    <span>{rec.trend_pct > 0 ? "+" : ""}{rec.trend_pct.toFixed(0)}%</span>
                  </div>
                </div>
              </div>
              {rec.warnings.length > 0 && (
                <div className="flex items-start gap-2 text-warning">
                  <AlertTriangle className="h-4 w-4 mt-0.5" />
                  <div>
                    {rec.warnings.map((w, i) => (
                      <p key={i}>{w}</p>
                    ))}
                  </div>
                </div>
              )}
              <p className="text-muted-foreground">{rec.reason_text}</p>
            </div>
          )}
        </div>

        <Button
          variant="ghost"
          size="icon"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </Button>
      </div>
    </div>
  )
}

function OrderSummary({
  recommendations,
  selected,
  quantities,
}: {
  recommendations: Recommendation[]
  selected: Set<string>
  quantities: Record<string, number>
}) {
  const selectedRecs = recommendations.filter((r) => selected.has(r.item_id))
  const totalItems = selectedRecs.length
  const totalSpend = selectedRecs.reduce((sum, r) => {
    const qty = quantities[r.item_id] ?? r.suggested_qty
    return sum + qty * (r.unit_cost || 0)
  }, 0)

  const byVendor = selectedRecs.reduce((acc, r) => {
    const vendor = r.vendor || "Unknown"
    const qty = quantities[r.item_id] ?? r.suggested_qty
    if (!acc[vendor]) acc[vendor] = { items: 0, spend: 0 }
    acc[vendor].items++
    acc[vendor].spend += qty * (r.unit_cost || 0)
    return acc
  }, {} as Record<string, { items: number; spend: number }>)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Order Summary</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Items</span>
          <span className="font-medium">{totalItems}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Total Spend</span>
          <span className="text-xl font-bold">{formatCurrency(totalSpend)}</span>
        </div>

        {Object.keys(byVendor).length > 0 && (
          <div className="pt-4 border-t space-y-2">
            <p className="text-sm font-medium">By Vendor</p>
            {Object.entries(byVendor).map(([vendor, data]) => (
              <div key={vendor} className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">{vendor}</span>
                <span>
                  {data.items} items • {formatCurrency(data.spend)}
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function OrderRecommendationsContent({ datasetId }: { datasetId: string }) {
  const queryClient = useQueryClient()
  const { addToast } = useToast()
  const { orderTargets, orderConstraints } = useAppStore()

  const [currentRun, setCurrentRun] = React.useState<RecommendationRun | null>(null)
  const [selected, setSelected] = React.useState<Set<string>>(new Set())
  const [quantities, setQuantities] = React.useState<Record<string, number>>({})
  const [groupBy, setGroupBy] = React.useState<"all" | "vendor" | "category">("all")

  const { data: runs, isLoading: loadingRuns } = useQuery({
    queryKey: ["recommendation-runs"],
    queryFn: () => api.getRecommendationRuns(),
  })

  const generateMutation = useMutation({
    mutationFn: () =>
      api.generateRecommendations({
        dataset_id: datasetId,
        targets: orderTargets,
        constraints: orderConstraints,
      }),
    onSuccess: (run) => {
      setCurrentRun(run)
      setSelected(new Set(run.recommendations.map((r) => r.item_id)))
      setQuantities({})
      queryClient.invalidateQueries({ queryKey: ["recommendation-runs"] })
      addToast({ title: "Recommendations generated", variant: "success" })
    },
    onError: () => {
      addToast({ title: "Failed to generate recommendations", variant: "destructive" })
    },
  })

  const approveMutation = useMutation({
    mutationFn: () =>
      api.approveRecommendations(currentRun!.run_id, {
        approved_items: Array.from(selected),
        modified_quantities: quantities,
        rejected_items: currentRun!.recommendations
          .filter((r) => !selected.has(r.item_id))
          .map((r) => r.item_id),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recommendation-runs"] })
      addToast({ title: "Order approved", variant: "success" })
    },
  })

  const handleExport = async () => {
    if (!currentRun) return
    try {
      const blob = await api.exportRecommendations(currentRun.run_id, "csv")
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `order-${currentRun.run_id}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      addToast({ title: "Failed to export", variant: "destructive" })
    }
  }

  const toggleItem = (itemId: string) => {
    const newSelected = new Set(selected)
    if (newSelected.has(itemId)) {
      newSelected.delete(itemId)
    } else {
      newSelected.add(itemId)
    }
    setSelected(newSelected)
  }

  const selectAll = () => {
    if (currentRun) {
      setSelected(new Set(currentRun.recommendations.map((r) => r.item_id)))
    }
  }

  const selectNone = () => {
    setSelected(new Set())
  }

  if (loadingRuns) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-12 w-48" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    )
  }

  if (!currentRun) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold">Order Recommendations</h2>
            <p className="text-sm text-muted-foreground">
              Generate smart ordering suggestions based on usage patterns
            </p>
          </div>
          <Button
            onClick={() => generateMutation.mutate()}
            loading={generateMutation.isPending}
          >
            <ShoppingCart className="mr-2 h-4 w-4" />
            Generate Recommendations
          </Button>
        </div>

        {runs && runs.length > 0 ? (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Previous Runs</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {runs.slice(0, 5).map((run) => (
                <button
                  key={run.run_id}
                  onClick={() => {
                    setCurrentRun(run)
                    setSelected(new Set(run.recommendations.map((r) => r.item_id)))
                  }}
                  className="w-full rounded-lg border p-4 text-left hover:bg-muted/50 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">
                        {new Date(run.created_at).toLocaleDateString()}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {run.total_items} items • {formatCurrency(run.total_spend)}
                      </p>
                    </div>
                    <Badge>{run.status}</Badge>
                  </div>
                </button>
              ))}
            </CardContent>
          </Card>
        ) : (
          <EmptyState
            icon={<ShoppingCart />}
            title="No recommendations yet"
            description="Generate your first order recommendations to optimize inventory."
          />
        )}
      </div>
    )
  }

  const recommendations = currentRun.recommendations
  const groupedRecs =
    groupBy === "all"
      ? { All: recommendations }
      : recommendations.reduce((acc, rec) => {
          const key = groupBy === "vendor" ? rec.vendor || "Unknown" : rec.category || "Unknown"
          if (!acc[key]) acc[key] = []
          acc[key].push(rec)
          return acc
        }, {} as Record<string, Recommendation[]>)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold">Order Recommendations</h2>
          <p className="text-sm text-muted-foreground">
            {new Date(currentRun.created_at).toLocaleDateString()} •{" "}
            {recommendations.length} items
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => setCurrentRun(null)}>
            New Run
          </Button>
          <Button variant="outline" onClick={handleExport}>
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>
          <Button
            onClick={() => approveMutation.mutate()}
            loading={approveMutation.isPending}
            disabled={selected.size === 0}
          >
            <Check className="mr-2 h-4 w-4" />
            Approve Order
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Recommendations List */}
        <div className="lg:col-span-2 space-y-4">
          {/* Controls */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" onClick={selectAll}>
                Select All
              </Button>
              <Button variant="ghost" size="sm" onClick={selectNone}>
                Select None
              </Button>
            </div>
            <Tabs value={groupBy} onValueChange={(v) => setGroupBy(v as typeof groupBy)}>
              <TabsList>
                <TabsTrigger value="all">All</TabsTrigger>
                <TabsTrigger value="vendor">Vendor</TabsTrigger>
                <TabsTrigger value="category">Category</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          {/* Items */}
          {Object.entries(groupedRecs).map(([group, recs]) => (
            <div key={group} className="space-y-2">
              {groupBy !== "all" && (
                <h3 className="font-medium text-muted-foreground">{group}</h3>
              )}
              {recs.map((rec) => (
                <RecommendationCard
                  key={rec.item_id}
                  rec={rec}
                  selected={selected.has(rec.item_id)}
                  onToggle={() => toggleItem(rec.item_id)}
                  onQuantityChange={(qty) =>
                    setQuantities((prev) => ({ ...prev, [rec.item_id]: qty }))
                  }
                  customQuantity={quantities[rec.item_id]}
                />
              ))}
            </div>
          ))}
        </div>

        {/* Summary Sidebar */}
        <div className="space-y-4">
          <OrderSummary
            recommendations={recommendations}
            selected={selected}
            quantities={quantities}
          />
        </div>
      </div>
    </div>
  )
}

export default function OrdersPage() {
  const activeDatasetId = useAppStore((state) => state.activeDatasetId)

  return (
    <PageLayout title="Orders">
      {activeDatasetId ? (
        <OrderRecommendationsContent datasetId={activeDatasetId} />
      ) : (
        <EmptyState
          icon={<Package />}
          title="No dataset selected"
          description="Select a dataset from the dashboard to generate order recommendations."
          action={
            <Link href="/">
              <Button>Go to Dashboard</Button>
            </Link>
          }
        />
      )}
    </PageLayout>
  )
}
