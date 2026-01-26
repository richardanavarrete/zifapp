"use client"

import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { useSearchParams, useRouter } from "next/navigation"
import {
  Search,
  Filter,
  ArrowUpDown,
  TrendingUp,
  TrendingDown,
  Minus,
  Package,
} from "lucide-react"
import Link from "next/link"
import { PageLayout } from "@/components/layout/page-layout"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Select } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { api } from "@/lib/api"
import { useAppStore } from "@/store/app"
import { formatNumber } from "@/lib/utils"
import type { Item, ItemStats, Dataset } from "@/types/api"

type ItemWithStats = Item & { stats: ItemStats }

function TrendIcon({ direction }: { direction: string }) {
  if (direction === "up") {
    return <TrendingUp className="h-4 w-4 text-success" />
  }
  if (direction === "down") {
    return <TrendingDown className="h-4 w-4 text-destructive" />
  }
  return <Minus className="h-4 w-4 text-muted-foreground" />
}

function StockBadge({ weeksOnHand }: { weeksOnHand: number }) {
  if (weeksOnHand < 1) {
    return <Badge variant="destructive">Critical</Badge>
  }
  if (weeksOnHand < 2) {
    return <Badge variant="warning">Low</Badge>
  }
  if (weeksOnHand > 6) {
    return <Badge variant="secondary">Overstock</Badge>
  }
  return <Badge variant="success">Good</Badge>
}

function InventoryTable({ items }: { items: ItemWithStats[] }) {
  return (
    <Card>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[300px]">Item</TableHead>
              <TableHead className="hidden md:table-cell">Category</TableHead>
              <TableHead className="text-right">On Hand</TableHead>
              <TableHead className="text-right hidden sm:table-cell">
                Avg Usage
              </TableHead>
              <TableHead className="text-right">Weeks Left</TableHead>
              <TableHead className="hidden lg:table-cell">Trend</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.item_id}>
                <TableCell>
                  <Link
                    href={`/inventory/${item.item_id}`}
                    className="font-medium hover:underline"
                  >
                    {item.name}
                  </Link>
                  <p className="text-xs text-muted-foreground md:hidden">
                    {item.category}
                  </p>
                </TableCell>
                <TableCell className="hidden md:table-cell text-muted-foreground">
                  {item.category || "-"}
                </TableCell>
                <TableCell className="text-right font-medium">
                  {formatNumber(item.stats.current_on_hand)}
                </TableCell>
                <TableCell className="text-right hidden sm:table-cell">
                  {formatNumber(item.stats.avg_usage)}
                </TableCell>
                <TableCell className="text-right">
                  {item.stats.weeks_on_hand.toFixed(1)}
                </TableCell>
                <TableCell className="hidden lg:table-cell">
                  <div className="flex items-center gap-1">
                    <TrendIcon direction={item.stats.trend_direction} />
                    <span className="text-xs text-muted-foreground">
                      {item.stats.trend_percent_change > 0 ? "+" : ""}
                      {item.stats.trend_percent_change.toFixed(0)}%
                    </span>
                  </div>
                </TableCell>
                <TableCell>
                  <StockBadge weeksOnHand={item.stats.weeks_on_hand} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </Card>
  )
}

function InventoryTableSkeleton() {
  return (
    <Card>
      <div className="p-4 space-y-4">
        {[...Array(10)].map((_, i) => (
          <div key={i} className="flex items-center gap-4">
            <Skeleton className="h-5 w-48" />
            <Skeleton className="h-5 w-24 hidden md:block" />
            <Skeleton className="h-5 w-16 ml-auto" />
            <Skeleton className="h-5 w-16 hidden sm:block" />
            <Skeleton className="h-5 w-12" />
            <Skeleton className="h-6 w-16" />
          </div>
        ))}
      </div>
    </Card>
  )
}

function InventoryContent({ datasetId }: { datasetId: string }) {
  const router = useRouter()
  const searchParams = useSearchParams()

  const [search, setSearch] = React.useState(searchParams.get("search") || "")
  const [category, setCategory] = React.useState(
    searchParams.get("category") || ""
  )
  const [sortBy, setSortBy] = React.useState(
    searchParams.get("sort_by") || "name"
  )
  const [sortOrder, setSortOrder] = React.useState<"asc" | "desc">(
    (searchParams.get("sort_order") as "asc" | "desc") || "asc"
  )

  const debouncedSearch = React.useDeferredValue(search)

  const { data: dataset } = useQuery({
    queryKey: ["dataset", datasetId],
    queryFn: () => api.getDataset(datasetId),
  })

  const { data, isLoading, error } = useQuery({
    queryKey: [
      "items",
      datasetId,
      debouncedSearch,
      category,
      sortBy,
      sortOrder,
    ],
    queryFn: () =>
      api.getItems(datasetId, {
        search: debouncedSearch || undefined,
        category: category || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
      }),
  })

  const handleSort = (field: string) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc")
    } else {
      setSortBy(field)
      setSortOrder("asc")
    }
  }

  const categories = dataset?.categories || []

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-col gap-4 sm:flex-row">
        <div className="flex-1">
          <Input
            placeholder="Search items..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            icon={<Search className="h-4 w-4" />}
          />
        </div>
        <div className="flex gap-2">
          <Select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            options={[
              { value: "", label: "All Categories" },
              ...categories.map((c) => ({ value: c, label: c })),
            ]}
            className="w-40"
          />
          <Select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            options={[
              { value: "name", label: "Name" },
              { value: "category", label: "Category" },
              { value: "on_hand", label: "On Hand" },
              { value: "weeks_on_hand", label: "Weeks Left" },
              { value: "avg_usage", label: "Usage" },
            ]}
            className="w-32"
          />
          <Button
            variant="outline"
            size="icon"
            onClick={() => setSortOrder(sortOrder === "asc" ? "desc" : "asc")}
          >
            <ArrowUpDown className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Results count */}
      {data && (
        <p className="text-sm text-muted-foreground">
          {data.total} items
          {debouncedSearch && ` matching "${debouncedSearch}"`}
          {category && ` in ${category}`}
        </p>
      )}

      {/* Table */}
      {isLoading ? (
        <InventoryTableSkeleton />
      ) : error || !data ? (
        <EmptyState
          icon={<Package />}
          title="Failed to load inventory"
          description="There was an error loading the inventory data."
          action={
            <Button onClick={() => window.location.reload()}>Retry</Button>
          }
        />
      ) : data.items.length === 0 ? (
        <EmptyState
          icon={<Search />}
          title="No items found"
          description={
            debouncedSearch || category
              ? "Try adjusting your search or filters."
              : "Upload inventory data to get started."
          }
          action={
            debouncedSearch || category ? (
              <Button
                variant="outline"
                onClick={() => {
                  setSearch("")
                  setCategory("")
                }}
              >
                Clear Filters
              </Button>
            ) : (
              <Link href="/upload">
                <Button>Upload Data</Button>
              </Link>
            )
          }
        />
      ) : (
        <InventoryTable items={data.items} />
      )}
    </div>
  )
}

function NoDatasetSelected() {
  return (
    <EmptyState
      icon={<Package />}
      title="No dataset selected"
      description="Select a dataset from the dashboard to view inventory."
      action={
        <Link href="/">
          <Button>Go to Dashboard</Button>
        </Link>
      }
    />
  )
}

export default function InventoryPage() {
  const activeDatasetId = useAppStore((state) => state.activeDatasetId)

  return (
    <PageLayout title="Inventory">
      {activeDatasetId ? (
        <React.Suspense fallback={<InventoryTableSkeleton />}>
          <InventoryContent datasetId={activeDatasetId} />
        </React.Suspense>
      ) : (
        <NoDatasetSelected />
      )}
    </PageLayout>
  )
}
