"use client"

import * as React from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Upload,
  File,
  X,
  Check,
  AlertTriangle,
  Trash2,
  FileSpreadsheet,
} from "lucide-react"
import { useRouter } from "next/navigation"
import { PageLayout } from "@/components/layout/page-layout"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { Progress } from "@/components/ui/progress"
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert"
import { useToast } from "@/hooks/use-toast"
import { api } from "@/lib/api"
import { useAppStore } from "@/store/app"
import { cn } from "@/lib/utils"
import type { Dataset, UploadResult } from "@/types/api"

function DropZone({
  onFileSelect,
  uploading,
}: {
  onFileSelect: (file: File) => void
  uploading: boolean
}) {
  const [dragActive, setDragActive] = React.useState(false)
  const inputRef = React.useRef<HTMLInputElement>(null)

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true)
    } else if (e.type === "dragleave") {
      setDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      onFileSelect(e.dataTransfer.files[0])
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      onFileSelect(e.target.files[0])
    }
  }

  return (
    <div
      className={cn(
        "relative rounded-lg border-2 border-dashed p-12 text-center transition-colors",
        dragActive
          ? "border-primary bg-primary/5"
          : "border-muted-foreground/25 hover:border-muted-foreground/50",
        uploading && "pointer-events-none opacity-50"
      )}
      onDragEnter={handleDrag}
      onDragLeave={handleDrag}
      onDragOver={handleDrag}
      onDrop={handleDrop}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".xlsx,.xls,.csv"
        onChange={handleChange}
        className="hidden"
      />
      <div className="flex flex-col items-center gap-4">
        <div className="rounded-full bg-muted p-4">
          <Upload className="h-8 w-8 text-muted-foreground" />
        </div>
        <div>
          <p className="text-lg font-medium">Drop your file here</p>
          <p className="text-sm text-muted-foreground">
            or{" "}
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="text-primary hover:underline"
            >
              browse files
            </button>
          </p>
        </div>
        <p className="text-xs text-muted-foreground">
          Supports Excel (.xlsx, .xls) and CSV files
        </p>
      </div>
    </div>
  )
}

function UploadProgress({ progress }: { progress: number }) {
  return (
    <Card>
      <CardContent className="py-8">
        <div className="flex flex-col items-center gap-4">
          <div className="relative">
            <FileSpreadsheet className="h-12 w-12 text-primary" />
          </div>
          <div className="w-full max-w-xs space-y-2">
            <Progress value={progress} />
            <p className="text-center text-sm text-muted-foreground">
              {progress < 100 ? "Uploading..." : "Processing..."}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function UploadResultCard({
  result,
  onViewDataset,
}: {
  result: UploadResult
  onViewDataset: () => void
}) {
  return (
    <Card className="border-success">
      <CardContent className="py-6">
        <div className="flex items-start gap-4">
          <div className="rounded-full bg-success/10 p-2">
            <Check className="h-6 w-6 text-success" />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold">Upload Successful</h3>
            <p className="text-sm text-muted-foreground mt-1">
              {result.filename}
            </p>
            <div className="flex flex-wrap gap-4 mt-4 text-sm">
              <div>
                <span className="text-muted-foreground">Items:</span>{" "}
                <span className="font-medium">{result.items_count}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Records:</span>{" "}
                <span className="font-medium">{result.records_count}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Periods:</span>{" "}
                <span className="font-medium">{result.periods_count}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Categories:</span>{" "}
                <span className="font-medium">
                  {result.categories_found.length}
                </span>
              </div>
            </div>
            {result.warnings.length > 0 && (
              <Alert variant="warning" className="mt-4">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Warnings</AlertTitle>
                <AlertDescription>
                  <ul className="list-disc list-inside">
                    {result.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </AlertDescription>
              </Alert>
            )}
            <div className="mt-4">
              <Button onClick={onViewDataset}>View Dataset</Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function DatasetCard({
  dataset,
  isActive,
  onSelect,
  onDelete,
}: {
  dataset: Dataset
  isActive: boolean
  onSelect: () => void
  onDelete: () => void
}) {
  return (
    <div
      className={cn(
        "rounded-lg border p-4 transition-colors",
        isActive && "border-primary bg-primary/5"
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <p className="font-medium">{dataset.name}</p>
            {isActive && <Badge variant="default">Active</Badge>}
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            {dataset.items_count} items • {dataset.periods_count} periods
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            {new Date(dataset.created_at).toLocaleDateString()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {!isActive && (
            <Button variant="outline" size="sm" onClick={onSelect}>
              Select
            </Button>
          )}
          <Button variant="ghost" size="icon" onClick={onDelete}>
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        </div>
      </div>
    </div>
  )
}

export default function UploadPage() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const { addToast } = useToast()
  const { activeDatasetId, setActiveDataset } = useAppStore()

  const [uploading, setUploading] = React.useState(false)
  const [progress, setProgress] = React.useState(0)
  const [uploadResult, setUploadResult] = React.useState<UploadResult | null>(null)

  const { data: datasets, isLoading } = useQuery({
    queryKey: ["datasets"],
    queryFn: () => api.getDatasets(),
  })

  const deleteMutation = useMutation({
    mutationFn: (datasetId: string) => api.deleteDataset(datasetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["datasets"] })
      addToast({ title: "Dataset deleted", variant: "success" })
    },
    onError: () => {
      addToast({ title: "Failed to delete dataset", variant: "destructive" })
    },
  })

  const handleFileSelect = async (file: File) => {
    setUploading(true)
    setProgress(0)
    setUploadResult(null)

    // Simulate progress
    const progressInterval = setInterval(() => {
      setProgress((prev) => Math.min(prev + 10, 90))
    }, 200)

    try {
      const result = await api.uploadInventory(file)
      setProgress(100)
      setUploadResult(result)
      queryClient.invalidateQueries({ queryKey: ["datasets"] })
      addToast({ title: "File uploaded successfully", variant: "success" })
    } catch (error) {
      addToast({
        title: "Upload failed",
        description: error instanceof Error ? error.message : "Unknown error",
        variant: "destructive",
      })
    } finally {
      clearInterval(progressInterval)
      setUploading(false)
    }
  }

  const handleViewDataset = async () => {
    if (uploadResult) {
      const dataset = await api.getDataset(uploadResult.dataset_id)
      setActiveDataset(dataset)
      router.push("/")
    }
  }

  const handleSelectDataset = async (dataset: Dataset) => {
    setActiveDataset(dataset)
    addToast({ title: `Switched to ${dataset.name}`, variant: "success" })
  }

  return (
    <PageLayout title="Upload">
      <div className="space-y-6">
        {/* Upload Section */}
        <Card>
          <CardHeader>
            <CardTitle>Upload Inventory Data</CardTitle>
          </CardHeader>
          <CardContent>
            {uploading ? (
              <UploadProgress progress={progress} />
            ) : uploadResult ? (
              <UploadResultCard
                result={uploadResult}
                onViewDataset={handleViewDataset}
              />
            ) : (
              <DropZone onFileSelect={handleFileSelect} uploading={uploading} />
            )}
          </CardContent>
        </Card>

        {/* Reset after successful upload */}
        {uploadResult && (
          <div className="flex justify-center">
            <Button
              variant="outline"
              onClick={() => setUploadResult(null)}
            >
              Upload Another File
            </Button>
          </div>
        )}

        {/* Existing Datasets */}
        <Card>
          <CardHeader>
            <CardTitle>Your Datasets</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-2">
                {[...Array(3)].map((_, i) => (
                  <Skeleton key={i} className="h-20 rounded-lg" />
                ))}
              </div>
            ) : datasets && datasets.length > 0 ? (
              <div className="space-y-2">
                {datasets.map((dataset) => (
                  <DatasetCard
                    key={dataset.dataset_id}
                    dataset={dataset}
                    isActive={dataset.dataset_id === activeDatasetId}
                    onSelect={() => handleSelectDataset(dataset)}
                    onDelete={() => deleteMutation.mutate(dataset.dataset_id)}
                  />
                ))}
              </div>
            ) : (
              <EmptyState
                icon={<File />}
                title="No datasets"
                description="Upload your first inventory file to get started."
              />
            )}
          </CardContent>
        </Card>
      </div>
    </PageLayout>
  )
}
