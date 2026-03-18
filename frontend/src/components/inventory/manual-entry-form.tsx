"use client"

import * as React from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus, Trash2, Pencil, Save, Package } from "lucide-react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useToast } from "@/hooks/use-toast"
import { api } from "@/lib/api"
import { useAppStore } from "@/store/app"
import type { ManualItemEntry, Dataset } from "@/types/api"

const UNIT_OPTIONS = [
  { value: "unit", label: "Unit" },
  { value: "bottle", label: "Bottle" },
  { value: "case", label: "Case" },
  { value: "keg", label: "Keg" },
  { value: "lb", label: "Pound (lb)" },
  { value: "oz", label: "Ounce (oz)" },
  { value: "each", label: "Each" },
  { value: "can", label: "Can" },
  { value: "box", label: "Box" },
]

interface FormItem extends ManualItemEntry {
  _tempId: string
}

const emptyForm: ManualItemEntry = {
  name: "",
  on_hand: 0,
  category: "",
  vendor: "",
  sku: "",
  unit_cost: undefined,
  unit_of_measure: "unit",
}

export function ManualEntryForm() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const { addToast } = useToast()
  const { setActiveDataset } = useAppStore()

  const nameInputRef = React.useRef<HTMLInputElement>(null)

  // Dataset selection
  const [datasetMode, setDatasetMode] = React.useState<"new" | "existing">("new")
  const [datasetName, setDatasetName] = React.useState("")
  const [selectedDatasetId, setSelectedDatasetId] = React.useState("")

  // Form state
  const [form, setForm] = React.useState<ManualItemEntry>({ ...emptyForm })
  const [editingId, setEditingId] = React.useState<string | null>(null)

  // Pending items list
  const [pendingItems, setPendingItems] = React.useState<FormItem[]>([])

  const { data: datasets } = useQuery({
    queryKey: ["datasets"],
    queryFn: () => api.getDatasets(),
  })

  const submitMutation = useMutation({
    mutationFn: () => {
      const items = pendingItems.map(({ _tempId, ...item }) => item)
      return api.submitManualEntry({
        dataset_name: datasetMode === "new" ? (datasetName || "Manual Entry") : undefined,
        dataset_id: datasetMode === "existing" ? selectedDatasetId : undefined,
        items,
      })
    },
    onSuccess: async (result) => {
      queryClient.invalidateQueries({ queryKey: ["datasets"] })
      setPendingItems([])
      setForm({ ...emptyForm })
      addToast({
        title: "Inventory saved",
        description: `${result.items_added} items, ${result.records_added} records added`,
        variant: "success",
      })

      // Navigate to dataset
      const dataset = await api.getDataset(result.dataset_id)
      setActiveDataset(dataset)
      router.push("/")
    },
    onError: (error) => {
      addToast({
        title: "Failed to save inventory",
        description: error instanceof Error ? error.message : "Unknown error",
        variant: "destructive",
      })
    },
  })

  const updateField = (field: keyof ManualItemEntry, value: string | number | undefined) => {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  const handleAddItem = () => {
    if (!form.name.trim()) {
      addToast({ title: "Item name is required", variant: "destructive" })
      nameInputRef.current?.focus()
      return
    }

    if (editingId) {
      // Update existing item in list
      setPendingItems((prev) =>
        prev.map((item) =>
          item._tempId === editingId
            ? { ...form, _tempId: editingId }
            : item
        )
      )
      setEditingId(null)
    } else {
      // Add new item
      const newItem: FormItem = {
        ...form,
        name: form.name.trim(),
        category: form.category?.trim() || undefined,
        vendor: form.vendor?.trim() || undefined,
        sku: form.sku?.trim() || undefined,
        _tempId: crypto.randomUUID(),
      }
      setPendingItems((prev) => [...prev, newItem])
    }

    // Clear form and refocus for quick-add
    setForm({ ...emptyForm })
    nameInputRef.current?.focus()
  }

  const handleEditItem = (item: FormItem) => {
    setForm({
      name: item.name,
      on_hand: item.on_hand,
      category: item.category || "",
      vendor: item.vendor || "",
      sku: item.sku || "",
      unit_cost: item.unit_cost,
      unit_of_measure: item.unit_of_measure || "unit",
    })
    setEditingId(item._tempId)
    nameInputRef.current?.focus()
  }

  const handleRemoveItem = (tempId: string) => {
    setPendingItems((prev) => prev.filter((item) => item._tempId !== tempId))
    if (editingId === tempId) {
      setEditingId(null)
      setForm({ ...emptyForm })
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault()
      handleAddItem()
    }
  }

  const canSubmit =
    pendingItems.length > 0 &&
    (datasetMode === "new" || selectedDatasetId) &&
    !submitMutation.isPending

  return (
    <div className="space-y-6">
      {/* Dataset Selection */}
      <div className="space-y-3">
        <label className="text-sm font-medium">Save to</label>
        <div className="flex gap-2">
          <Button
            type="button"
            variant={datasetMode === "new" ? "default" : "outline"}
            size="sm"
            onClick={() => setDatasetMode("new")}
          >
            New Dataset
          </Button>
          <Button
            type="button"
            variant={datasetMode === "existing" ? "default" : "outline"}
            size="sm"
            onClick={() => setDatasetMode("existing")}
            disabled={!datasets || datasets.length === 0}
          >
            Existing Dataset
          </Button>
        </div>
        {datasetMode === "new" ? (
          <Input
            placeholder="Dataset name (e.g. Weekly Count 3/18)"
            value={datasetName}
            onChange={(e) => setDatasetName(e.target.value)}
          />
        ) : (
          <Select
            value={selectedDatasetId}
            onChange={(e) => setSelectedDatasetId(e.target.value)}
            placeholder="Select a dataset"
            options={
              datasets?.map((d) => ({
                value: d.dataset_id,
                label: `${d.name} (${d.items_count} items)`,
              })) || []
            }
          />
        )}
      </div>

      {/* Item Entry Form */}
      <div className="space-y-3 rounded-lg border p-4">
        <div className="flex items-center justify-between">
          <label className="text-sm font-medium">
            {editingId ? "Edit Item" : "Add Item"}
          </label>
          {editingId && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                setEditingId(null)
                setForm({ ...emptyForm })
              }}
            >
              Cancel Edit
            </Button>
          )}
        </div>

        {/* Row 1: Name + Quantity */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_120px]">
          <Input
            ref={nameInputRef}
            placeholder="Item name *"
            value={form.name}
            onChange={(e) => updateField("name", e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <Input
            type="number"
            placeholder="Qty on hand *"
            min={0}
            step="any"
            value={form.on_hand || ""}
            onChange={(e) =>
              updateField("on_hand", e.target.value ? parseFloat(e.target.value) : 0)
            }
            onKeyDown={handleKeyDown}
          />
        </div>

        {/* Row 2: Category, Vendor, Unit */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Input
            placeholder="Category"
            value={form.category || ""}
            onChange={(e) => updateField("category", e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <Input
            placeholder="Vendor"
            value={form.vendor || ""}
            onChange={(e) => updateField("vendor", e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <Select
            value={form.unit_of_measure || "unit"}
            onChange={(e) => updateField("unit_of_measure", e.target.value)}
            options={UNIT_OPTIONS}
          />
        </div>

        {/* Row 3: Cost, SKU */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-[120px_1fr_auto]">
          <Input
            type="number"
            placeholder="Unit cost"
            min={0}
            step="0.01"
            value={form.unit_cost ?? ""}
            onChange={(e) =>
              updateField(
                "unit_cost",
                e.target.value ? parseFloat(e.target.value) : undefined
              )
            }
            onKeyDown={handleKeyDown}
          />
          <Input
            placeholder="SKU (optional)"
            value={form.sku || ""}
            onChange={(e) => updateField("sku", e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <Button type="button" onClick={handleAddItem}>
            {editingId ? (
              <>
                <Save className="mr-2 h-4 w-4" />
                Update
              </>
            ) : (
              <>
                <Plus className="mr-2 h-4 w-4" />
                Add
              </>
            )}
          </Button>
        </div>

        <p className="text-xs text-muted-foreground">
          Press Enter to quickly add items. Name and quantity are required.
        </p>
      </div>

      {/* Pending Items List */}
      {pendingItems.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium">
                Items to Save
              </label>
              <Badge variant="secondary">{pendingItems.length}</Badge>
            </div>
            <span className="text-sm text-muted-foreground">
              {pendingItems.reduce((sum, i) => sum + i.on_hand, 0).toFixed(1)} total
              units
            </span>
          </div>

          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Item</TableHead>
                  <TableHead className="hidden sm:table-cell">Category</TableHead>
                  <TableHead className="text-right">Qty</TableHead>
                  <TableHead className="hidden sm:table-cell">Unit</TableHead>
                  <TableHead className="hidden sm:table-cell text-right">Cost</TableHead>
                  <TableHead className="w-[80px]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {pendingItems.map((item) => (
                  <TableRow key={item._tempId}>
                    <TableCell className="font-medium">
                      {item.name}
                      {item.vendor && (
                        <span className="block text-xs text-muted-foreground">
                          {item.vendor}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="hidden sm:table-cell">
                      {item.category || "—"}
                    </TableCell>
                    <TableCell className="text-right">{item.on_hand}</TableCell>
                    <TableCell className="hidden sm:table-cell">
                      {item.unit_of_measure || "unit"}
                    </TableCell>
                    <TableCell className="hidden sm:table-cell text-right">
                      {item.unit_cost != null ? `$${item.unit_cost.toFixed(2)}` : "—"}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => handleEditItem(item)}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => handleRemoveItem(item._tempId)}
                        >
                          <Trash2 className="h-3.5 w-3.5 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <Button
            className="w-full"
            size="lg"
            disabled={!canSubmit}
            onClick={() => submitMutation.mutate()}
          >
            <Package className="mr-2 h-4 w-4" />
            {submitMutation.isPending
              ? "Saving..."
              : `Save ${pendingItems.length} Item${pendingItems.length !== 1 ? "s" : ""}`}
          </Button>
        </div>
      )}

      {/* Empty state */}
      {pendingItems.length === 0 && (
        <div className="rounded-lg border border-dashed p-8 text-center">
          <Package className="mx-auto h-8 w-8 text-muted-foreground" />
          <p className="mt-2 text-sm text-muted-foreground">
            Add items above to build your inventory count
          </p>
        </div>
      )}
    </div>
  )
}
