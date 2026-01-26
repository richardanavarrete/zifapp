"use client"

import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { useParams } from "next/navigation"
import {
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  Minus,
  Package,
  Calendar,
  AlertTriangle,
} from "lucide-react"
import Link from "next/link"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from "recharts"
import { PageLayout } from "@/components/layout/page-layout"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { api } from "@/lib/api"
import { useAppStore } from "@/store/app"
import { formatNumber, formatCurrency } from "@/lib/utils"

function StatCard({
  title,
  value,
  subtitle,
}: {
  title: string
  value: string | number
  subtitle?: string
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-sm text-muted-foreground">{title}</p>
        <p className="text-2xl font-bold">{value}</p>
        {subtitle && (
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        )}
      </CardContent>
    </Card>
  )
}

function TrendBadge({
  direction,
  percent,
}: {
  direction: string
  percent: number
}) {
  if (direction === "up") {
    return (
      <Badge variant="default" className="gap-1">
        <TrendingUp className="h-3 w-3" />
        +{percent.toFixed(0)}%
      </Badge>
    )
  }
  if (direction === "down") {
    return (
      <Badge variant="secondary" className="gap-1">
        <TrendingDown className="h-3 w-3" />
        {percent.toFixed(0)}%
      </Badge>
    )
  }
  return (
    <Badge variant="outline" className="gap-1">
      <Minus className="h-3 w-3" />
      Stable
    </Badge>
  )
}

function UsageChart({
  history,
}: {
  history: { period: string; usage: number; on_hand: number }[]
}) {
  const chartData = history.map((h) => ({
    ...h,
    period: h.period.slice(5), // Shorten date for display
  }))

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Usage History</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis
                dataKey="period"
                className="text-xs"
                tick={{ fill: "hsl(var(--muted-foreground))" }}
              />
              <YAxis
                className="text-xs"
                tick={{ fill: "hsl(var(--muted-foreground))" }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                }}
              />
              <Area
                type="monotone"
                dataKey="usage"
                stroke="hsl(var(--primary))"
                fill="hsl(var(--primary) / 0.2)"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}

function OnHandChart({
  history,
}: {
  history: { period: string; usage: number; on_hand: number }[]
}) {
  const chartData = history.map((h) => ({
    ...h,
    period: h.period.slice(5),
  }))

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">On Hand Levels</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis
                dataKey="period"
                className="text-xs"
                tick={{ fill: "hsl(var(--muted-foreground))" }}
              />
              <YAxis
                className="text-xs"
                tick={{ fill: "hsl(var(--muted-foreground))" }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                }}
              />
              <Line
                type="monotone"
                dataKey="on_hand"
                stroke="hsl(var(--success))"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}

function ItemDetailContent({
  datasetId,
  itemId,
}: {
  datasetId: string
  itemId: string
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["item", datasetId, itemId],
    queryFn: () => api.getItem(datasetId, itemId),
  })

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </div>
        <Skeleton className="h-80 rounded-xl" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <EmptyState
        icon={<AlertTriangle />}
        title="Item not found"
        description="The requested item could not be found."
        action={
          <Link href="/inventory">
            <Button>Back to Inventory</Button>
          </Link>
        }
      />
    )
  }

  const { item, stats, history } = data

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Link
            href="/inventory"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-2"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Inventory
          </Link>
          <h1 className="text-2xl font-bold">{item.name}</h1>
          <div className="flex items-center gap-2 mt-1">
            {item.category && (
              <Badge variant="secondary">{item.category}</Badge>
            )}
            {item.vendor && (
              <span className="text-sm text-muted-foreground">
                {item.vendor}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <TrendBadge
            direction={stats.trend_direction}
            percent={stats.trend_percent_change}
          />
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Current On Hand"
          value={formatNumber(stats.current_on_hand)}
          subtitle={item.unit_of_measure || "units"}
        />
        <StatCard
          title="Avg Weekly Usage"
          value={formatNumber(stats.avg_usage)}
          subtitle={`Min: ${formatNumber(stats.min_usage)} / Max: ${formatNumber(stats.max_usage)}`}
        />
        <StatCard
          title="Weeks on Hand"
          value={stats.weeks_on_hand.toFixed(1)}
          subtitle={`${stats.days_on_hand.toFixed(0)} days`}
        />
        <StatCard
          title="Unit Cost"
          value={item.unit_cost ? formatCurrency(item.unit_cost) : "-"}
          subtitle={item.sku ? `SKU: ${item.sku}` : undefined}
        />
      </div>

      {/* Alerts */}
      {(stats.has_negative_usage || stats.has_gaps || stats.weeks_on_hand < 2) && (
        <Card className="border-warning">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-warning mt-0.5" />
              <div className="space-y-1">
                {stats.weeks_on_hand < 1 && (
                  <p className="text-sm font-medium">
                    Critical stock level - may run out soon
                  </p>
                )}
                {stats.weeks_on_hand >= 1 && stats.weeks_on_hand < 2 && (
                  <p className="text-sm font-medium">
                    Low stock - consider reordering
                  </p>
                )}
                {stats.has_negative_usage && (
                  <p className="text-sm text-muted-foreground">
                    Data includes negative usage values
                  </p>
                )}
                {stats.has_gaps && (
                  <p className="text-sm text-muted-foreground">
                    Missing data in some periods
                  </p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Charts */}
      {history.length > 0 ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <UsageChart history={history} />
          <OnHandChart history={history} />
        </div>
      ) : (
        <Card>
          <CardContent className="py-12">
            <EmptyState
              icon={<Calendar />}
              title="No history data"
              description="Historical data will appear here once available."
            />
          </CardContent>
        </Card>
      )}

      {/* Additional Info */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Item Details</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <dt className="text-sm text-muted-foreground">Item ID</dt>
              <dd className="font-mono text-sm">{item.item_id}</dd>
            </div>
            {item.subcategory && (
              <div>
                <dt className="text-sm text-muted-foreground">Subcategory</dt>
                <dd>{item.subcategory}</dd>
              </div>
            )}
            {item.location && (
              <div>
                <dt className="text-sm text-muted-foreground">Location</dt>
                <dd>{item.location}</dd>
              </div>
            )}
            <div>
              <dt className="text-sm text-muted-foreground">Record Count</dt>
              <dd>{stats.record_count} periods</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">Usage Variance</dt>
              <dd>
                CV: {(stats.coefficient_of_variation * 100).toFixed(0)}%
              </dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">Total Usage</dt>
              <dd>{formatNumber(stats.total_usage)}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>
    </div>
  )
}

export default function ItemDetailPage() {
  const params = useParams()
  const itemId = params.itemId as string
  const activeDatasetId = useAppStore((state) => state.activeDatasetId)

  if (!activeDatasetId) {
    return (
      <PageLayout>
        <EmptyState
          icon={<Package />}
          title="No dataset selected"
          description="Select a dataset from the dashboard to view item details."
          action={
            <Link href="/">
              <Button>Go to Dashboard</Button>
            </Link>
          }
        />
      </PageLayout>
    )
  }

  return (
    <PageLayout>
      <ItemDetailContent datasetId={activeDatasetId} itemId={itemId} />
    </PageLayout>
  )
}
