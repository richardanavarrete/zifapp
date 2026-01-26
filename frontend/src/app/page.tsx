"use client"

import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import {
  Package,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  ArrowRight,
  Upload,
} from "lucide-react"
import Link from "next/link"
import { PageLayout } from "@/components/layout/page-layout"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { api } from "@/lib/api"
import { useAppStore } from "@/store/app"
import { formatNumber } from "@/lib/utils"
import type { DashboardData, Dataset } from "@/types/api"

function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
}: {
  title: string
  value: string | number
  subtitle?: string
  icon: React.ElementType
  trend?: { value: number; label: string }
}) {
  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <p className="mt-1 text-2xl font-bold">{value}</p>
            {subtitle && (
              <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p>
            )}
            {trend && (
              <div className="mt-2 flex items-center gap-1 text-xs">
                {trend.value >= 0 ? (
                  <TrendingUp className="h-3 w-3 text-success" />
                ) : (
                  <TrendingDown className="h-3 w-3 text-destructive" />
                )}
                <span
                  className={
                    trend.value >= 0 ? "text-success" : "text-destructive"
                  }
                >
                  {trend.value >= 0 ? "+" : ""}
                  {trend.value}%
                </span>
                <span className="text-muted-foreground">{trend.label}</span>
              </div>
            )}
          </div>
          <div className="rounded-lg bg-primary/10 p-3">
            <Icon className="h-5 w-5 text-primary" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function StatCardSkeleton() {
  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-8 w-24" />
            <Skeleton className="h-3 w-32" />
          </div>
          <Skeleton className="h-11 w-11 rounded-lg" />
        </div>
      </CardContent>
    </Card>
  )
}

function AlertsSection({ alerts }: { alerts: DashboardData["alerts"] }) {
  const criticalAlerts = alerts.filter((a) => a.severity === "critical")
  const warningAlerts = alerts.filter((a) => a.severity === "warning")
  const infoAlerts = alerts.filter((a) => a.severity === "info")

  const sortedAlerts = [...criticalAlerts, ...warningAlerts, ...infoAlerts]

  if (sortedAlerts.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Alerts</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No alerts at this time
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-base">Alerts</CardTitle>
        <Badge variant={criticalAlerts.length > 0 ? "destructive" : "secondary"}>
          {sortedAlerts.length}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        {sortedAlerts.slice(0, 5).map((alert, i) => (
          <div
            key={i}
            className="flex items-start gap-3 rounded-lg border p-3"
          >
            <AlertTriangle
              className={`h-4 w-4 mt-0.5 ${
                alert.severity === "critical"
                  ? "text-destructive"
                  : alert.severity === "warning"
                  ? "text-warning"
                  : "text-muted-foreground"
              }`}
            />
            <div className="flex-1 space-y-1">
              <p className="text-sm font-medium">{alert.title}</p>
              <p className="text-xs text-muted-foreground">{alert.message}</p>
            </div>
          </div>
        ))}
        {sortedAlerts.length > 5 && (
          <Button variant="ghost" size="sm" className="w-full">
            View all {sortedAlerts.length} alerts
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

function QuickActions() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Quick Actions</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2">
        <Link href="/voice">
          <Button variant="outline" className="w-full justify-start gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/10">
              <Package className="h-4 w-4 text-primary" />
            </div>
            <div className="text-left">
              <p className="text-sm font-medium">Voice Count</p>
              <p className="text-xs text-muted-foreground">
                Start counting inventory
              </p>
            </div>
            <ArrowRight className="ml-auto h-4 w-4" />
          </Button>
        </Link>
        <Link href="/orders">
          <Button variant="outline" className="w-full justify-start gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/10">
              <TrendingUp className="h-4 w-4 text-primary" />
            </div>
            <div className="text-left">
              <p className="text-sm font-medium">Order Recommendations</p>
              <p className="text-xs text-muted-foreground">
                Generate order list
              </p>
            </div>
            <ArrowRight className="ml-auto h-4 w-4" />
          </Button>
        </Link>
        <Link href="/upload">
          <Button variant="outline" className="w-full justify-start gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/10">
              <Upload className="h-4 w-4 text-primary" />
            </div>
            <div className="text-left">
              <p className="text-sm font-medium">Upload Data</p>
              <p className="text-xs text-muted-foreground">
                Import inventory file
              </p>
            </div>
            <ArrowRight className="ml-auto h-4 w-4" />
          </Button>
        </Link>
      </CardContent>
    </Card>
  )
}

function LowStockItems({
  items,
}: {
  items: DashboardData["low_stock_items"]
}) {
  if (items.length === 0) {
    return null
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-base">Low Stock Items</CardTitle>
        <Link href="/inventory?filter=low_stock">
          <Button variant="ghost" size="sm">
            View all
          </Button>
        </Link>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {items.slice(0, 5).map((item) => (
            <Link
              key={item.item_id}
              href={`/inventory/${item.item_id}`}
              className="flex items-center justify-between rounded-lg border p-3 hover:bg-muted/50 transition-colors"
            >
              <div>
                <p className="text-sm font-medium">{item.name}</p>
                <p className="text-xs text-muted-foreground">{item.category}</p>
              </div>
              <div className="text-right">
                <Badge
                  variant={
                    item.stats.weeks_on_hand < 1 ? "destructive" : "warning"
                  }
                >
                  {item.stats.weeks_on_hand.toFixed(1)}w left
                </Badge>
              </div>
            </Link>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function CategoryBreakdown({
  categories,
}: {
  categories: DashboardData["categories"]
}) {
  type CategoryData = { items: number; on_hand: number; usage: number }
  const categoryList = (Object.entries(categories) as [string, CategoryData][])
    .map(([name, data]) => ({ name, items: data.items, on_hand: data.on_hand, usage: data.usage }))
    .sort((a, b) => b.usage - a.usage)

  if (categoryList.length === 0) {
    return null
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Categories</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {categoryList.slice(0, 6).map((cat) => (
            <div key={cat.name} className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">{cat.name}</span>
                <span className="text-muted-foreground">
                  {cat.items} items
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full bg-primary transition-all"
                    style={{
                      width: `${Math.min(100, (cat.on_hand / (cat.usage || 1)) * 20)}%`,
                    }}
                  />
                </div>
                <span className="text-xs text-muted-foreground w-16 text-right">
                  {formatNumber(cat.on_hand)}
                </span>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function DashboardContent({ datasetId }: { datasetId: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard", datasetId],
    queryFn: () => api.getDashboard(datasetId),
  })

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <StatCardSkeleton key={i} />
          ))}
        </div>
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <Skeleton className="h-64 rounded-xl" />
          </div>
          <Skeleton className="h-64 rounded-xl" />
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <EmptyState
        icon={<AlertTriangle />}
        title="Failed to load dashboard"
        description="There was an error loading the dashboard data. Please try again."
        action={
          <Button onClick={() => window.location.reload()}>Retry</Button>
        }
      />
    )
  }

  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Items"
          value={formatNumber(data.total_items)}
          subtitle={`${Object.keys(data.categories).length} categories`}
          icon={Package}
        />
        <StatCard
          title="On Hand"
          value={formatNumber(data.total_on_hand)}
          subtitle="Total units"
          icon={Package}
        />
        <StatCard
          title="Weekly Usage"
          value={formatNumber(data.total_usage / Math.max(1, data.periods_count))}
          subtitle="Average per week"
          icon={TrendingUp}
        />
        <StatCard
          title="Date Range"
          value={data.periods_count}
          subtitle={
            data.date_range_start && data.date_range_end
              ? `${data.date_range_start} - ${data.date_range_end}`
              : "periods"
          }
          icon={Package}
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <AlertsSection alerts={data.alerts} />
          <LowStockItems items={data.low_stock_items} />
        </div>
        <div className="space-y-6">
          <QuickActions />
          <CategoryBreakdown categories={data.categories} />
        </div>
      </div>
    </div>
  )
}

function NoDatasetSelected() {
  const { data: datasets, isLoading } = useQuery({
    queryKey: ["datasets"],
    queryFn: () => api.getDatasets(),
  })

  const setActiveDataset = useAppStore((state) => state.setActiveDataset)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Skeleton className="h-64 w-full max-w-md rounded-xl" />
      </div>
    )
  }

  if (!datasets || datasets.length === 0) {
    return (
      <EmptyState
        icon={<Upload />}
        title="No data yet"
        description="Upload your first inventory file to get started with tracking and recommendations."
        action={
          <Link href="/upload">
            <Button>
              <Upload className="mr-2 h-4 w-4" />
              Upload Inventory
            </Button>
          </Link>
        }
      />
    )
  }

  return (
    <div className="mx-auto max-w-md space-y-6">
      <div className="text-center">
        <h2 className="text-lg font-semibold">Select a Dataset</h2>
        <p className="text-sm text-muted-foreground">
          Choose a dataset to view the dashboard
        </p>
      </div>
      <div className="space-y-2">
        {datasets.map((dataset: Dataset) => (
          <button
            key={dataset.dataset_id}
            onClick={() => setActiveDataset(dataset)}
            className="w-full rounded-lg border p-4 text-left hover:bg-muted/50 transition-colors"
          >
            <p className="font-medium">{dataset.name}</p>
            <p className="text-sm text-muted-foreground">
              {dataset.items_count} items &middot; {dataset.periods_count}{" "}
              periods
            </p>
          </button>
        ))}
      </div>
      <div className="text-center">
        <Link href="/upload">
          <Button variant="outline">
            <Upload className="mr-2 h-4 w-4" />
            Upload New Dataset
          </Button>
        </Link>
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const activeDatasetId = useAppStore((state) => state.activeDatasetId)

  return (
    <PageLayout title="Dashboard">
      {activeDatasetId ? (
        <DashboardContent datasetId={activeDatasetId} />
      ) : (
        <NoDatasetSelected />
      )}
    </PageLayout>
  )
}
