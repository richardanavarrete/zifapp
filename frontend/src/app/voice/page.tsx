"use client"

import * as React from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Mic,
  MicOff,
  Square,
  Check,
  X,
  Edit2,
  Trash2,
  Download,
  Plus,
  Package,
} from "lucide-react"
import Link from "next/link"
import { PageLayout } from "@/components/layout/page-layout"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { useToast } from "@/hooks/use-toast"
import { api } from "@/lib/api"
import { useAppStore } from "@/store/app"
import { cn } from "@/lib/utils"
import type { VoiceSession, CountRecord, ParsedVoiceInput } from "@/types/api"

function RecordButton({
  isRecording,
  onStart,
  onStop,
  disabled,
}: {
  isRecording: boolean
  onStart: () => void
  onStop: () => void
  disabled?: boolean
}) {
  return (
    <button
      onClick={isRecording ? onStop : onStart}
      disabled={disabled}
      className={cn(
        "relative flex h-32 w-32 items-center justify-center rounded-full transition-all",
        isRecording
          ? "bg-destructive text-destructive-foreground animate-pulse"
          : "bg-primary text-primary-foreground hover:bg-primary/90",
        disabled && "opacity-50 cursor-not-allowed"
      )}
    >
      {isRecording ? (
        <Square className="h-12 w-12" />
      ) : (
        <Mic className="h-12 w-12" />
      )}
      {isRecording && (
        <span className="absolute -bottom-8 text-sm font-medium text-destructive">
          Recording...
        </span>
      )}
    </button>
  )
}

function CountRecordItem({
  record,
  onConfirm,
  onEdit,
  onDelete,
}: {
  record: CountRecord
  onConfirm: () => void
  onEdit: () => void
  onDelete: () => void
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-4 rounded-lg border p-4",
        record.confirmed ? "bg-muted/50" : "bg-background",
        record.match_confidence < 0.7 && !record.confirmed && "border-warning"
      )}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="font-medium truncate">
            {record.item_name || "Unknown Item"}
          </p>
          {record.match_confidence < 0.7 && !record.confirmed && (
            <Badge variant="warning">Review</Badge>
          )}
          {record.confirmed && (
            <Badge variant="success">Confirmed</Badge>
          )}
        </div>
        <p className="text-sm text-muted-foreground truncate">
          {record.raw_text}
        </p>
        <p className="text-lg font-bold mt-1">
          {record.quantity} {record.unit || "units"}
        </p>
      </div>
      <div className="flex items-center gap-2">
        {!record.confirmed && (
          <Button variant="ghost" size="icon" onClick={onConfirm}>
            <Check className="h-4 w-4 text-success" />
          </Button>
        )}
        <Button variant="ghost" size="icon" onClick={onEdit}>
          <Edit2 className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" onClick={onDelete}>
          <Trash2 className="h-4 w-4 text-destructive" />
        </Button>
      </div>
    </div>
  )
}

function EditRecordDialog({
  record,
  open,
  onOpenChange,
  onSave,
}: {
  record: CountRecord | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSave: (data: Partial<CountRecord>) => void
}) {
  const [itemName, setItemName] = React.useState("")
  const [quantity, setQuantity] = React.useState("")
  const [unit, setUnit] = React.useState("")

  React.useEffect(() => {
    if (record) {
      setItemName(record.item_name || "")
      setQuantity(record.quantity.toString())
      setUnit(record.unit || "")
    }
  }, [record])

  const handleSave = () => {
    onSave({
      item_name: itemName,
      quantity: parseFloat(quantity) || 0,
      unit: unit || undefined,
      manually_edited: true,
    })
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Count</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Item Name</label>
            <Input
              value={itemName}
              onChange={(e) => setItemName(e.target.value)}
              placeholder="Enter item name"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Quantity</label>
              <Input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="0"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Unit</label>
              <Input
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                placeholder="bottles, cases, etc."
              />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave}>Save Changes</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function NewSessionDialog({
  open,
  onOpenChange,
  onCreate,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreate: (name: string, location?: string) => void
}) {
  const [name, setName] = React.useState("")
  const [location, setLocation] = React.useState("")

  const handleCreate = () => {
    onCreate(name || `Count ${new Date().toLocaleDateString()}`, location || undefined)
    setName("")
    setLocation("")
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New Counting Session</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Session Name</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={`Count ${new Date().toLocaleDateString()}`}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Location (optional)</label>
            <Input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g., Main Bar, Kitchen"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleCreate}>Create Session</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function VoiceCountingContent({ datasetId }: { datasetId: string }) {
  const queryClient = useQueryClient()
  const { addToast } = useToast()

  const [activeSession, setActiveSession] = React.useState<VoiceSession | null>(null)
  const [isRecording, setIsRecording] = React.useState(false)
  const [showNewSession, setShowNewSession] = React.useState(false)
  const [editingRecord, setEditingRecord] = React.useState<CountRecord | null>(null)
  const [transcribing, setTranscribing] = React.useState(false)
  const [mediaRecorder, setMediaRecorder] = React.useState<MediaRecorder | null>(null)

  const { data: sessions, isLoading: loadingSessions } = useQuery({
    queryKey: ["voice-sessions"],
    queryFn: () => api.getVoiceSessions("in_progress"),
  })

  const { data: records, refetch: refetchRecords } = useQuery({
    queryKey: ["voice-records", activeSession?.session_id],
    queryFn: () =>
      activeSession ? api.getCountRecords(activeSession.session_id) : Promise.resolve([]),
    enabled: !!activeSession,
  })

  const createSession = useMutation({
    mutationFn: (data: { name: string; location?: string }) =>
      api.createVoiceSession({ ...data, dataset_id: datasetId }),
    onSuccess: (session) => {
      setActiveSession(session)
      queryClient.invalidateQueries({ queryKey: ["voice-sessions"] })
      addToast({ title: "Session created", variant: "success" })
    },
    onError: () => {
      addToast({ title: "Failed to create session", variant: "destructive" })
    },
  })

  const confirmRecord = useMutation({
    mutationFn: (recordId: string) =>
      api.confirmCountRecord(activeSession!.session_id, recordId),
    onSuccess: () => {
      refetchRecords()
    },
  })

  const updateRecord = useMutation({
    mutationFn: ({
      recordId,
      data,
    }: {
      recordId: string
      data: Partial<CountRecord>
    }) => api.updateCountRecord(activeSession!.session_id, recordId, data),
    onSuccess: () => {
      refetchRecords()
      addToast({ title: "Record updated", variant: "success" })
    },
  })

  const completeSession = useMutation({
    mutationFn: () => api.completeVoiceSession(activeSession!.session_id),
    onSuccess: () => {
      setActiveSession(null)
      queryClient.invalidateQueries({ queryKey: ["voice-sessions"] })
      addToast({ title: "Session completed", variant: "success" })
    },
  })

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      const chunks: Blob[] = []

      recorder.ondataavailable = (e) => chunks.push(e.data)
      recorder.onstop = async () => {
        const blob = new Blob(chunks, { type: "audio/webm" })
        const file = new File([blob], "recording.webm", { type: "audio/webm" })
        await processAudio(file)
        stream.getTracks().forEach((track) => track.stop())
      }

      recorder.start()
      setMediaRecorder(recorder)
      setIsRecording(true)
    } catch (error) {
      addToast({
        title: "Microphone access denied",
        description: "Please allow microphone access to use voice counting.",
        variant: "destructive",
      })
    }
  }

  const stopRecording = () => {
    if (mediaRecorder) {
      mediaRecorder.stop()
      setMediaRecorder(null)
      setIsRecording(false)
    }
  }

  const processAudio = async (file: File) => {
    if (!activeSession) return

    setTranscribing(true)
    try {
      const transcription = await api.transcribeAudio(file)

      if (transcription.text) {
        const match = await api.matchVoiceInput({
          text: transcription.text,
          dataset_id: datasetId,
          session_id: activeSession.session_id,
        })

        await api.addCountRecord(activeSession.session_id, {
          raw_text: transcription.text,
          item_id: match.best_match?.item_id,
          item_name: match.best_match?.item_name || match.item_text,
          quantity: match.quantity,
          unit: match.unit,
          match_confidence: match.best_match?.score || 0,
          match_method: match.best_match?.match_type || "manual",
        })

        refetchRecords()
        addToast({ title: "Count recorded", variant: "success" })
      }
    } catch (error) {
      addToast({
        title: "Failed to process audio",
        variant: "destructive",
      })
    } finally {
      setTranscribing(false)
    }
  }

  const handleExport = async () => {
    if (!activeSession) return
    try {
      const exportData = await api.exportSession(activeSession.session_id, "csv")
      const blob = new Blob([exportData.csv_text], { type: "text/csv" })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `${activeSession.name}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch (error) {
      addToast({ title: "Failed to export", variant: "destructive" })
    }
  }

  if (loadingSessions) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-48 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    )
  }

  // No active session - show session picker or create new
  if (!activeSession) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Voice Counting</h2>
          <Button onClick={() => setShowNewSession(true)}>
            <Plus className="mr-2 h-4 w-4" />
            New Session
          </Button>
        </div>

        {sessions && sessions.length > 0 ? (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Resume Session</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {sessions.map((session) => (
                <button
                  key={session.session_id}
                  onClick={() => setActiveSession(session)}
                  className="w-full rounded-lg border p-4 text-left hover:bg-muted/50 transition-colors"
                >
                  <p className="font-medium">{session.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {session.items_counted} items &middot;{" "}
                    {new Date(session.updated_at).toLocaleString()}
                  </p>
                </button>
              ))}
            </CardContent>
          </Card>
        ) : (
          <EmptyState
            icon={<Mic />}
            title="No active sessions"
            description="Start a new counting session to begin voice-based inventory counting."
            action={
              <Button onClick={() => setShowNewSession(true)}>
                <Plus className="mr-2 h-4 w-4" />
                New Session
              </Button>
            }
          />
        )}

        <NewSessionDialog
          open={showNewSession}
          onOpenChange={setShowNewSession}
          onCreate={(name, location) =>
            createSession.mutate({ name, location })
          }
        />
      </div>
    )
  }

  // Active session view
  return (
    <div className="space-y-6">
      {/* Session Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold">{activeSession.name}</h2>
          <p className="text-sm text-muted-foreground">
            {activeSession.items_counted} items counted
            {activeSession.location && ` • ${activeSession.location}`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setActiveSession(null)}
          >
            Switch Session
          </Button>
          <Button
            variant="default"
            size="sm"
            onClick={() => completeSession.mutate()}
          >
            <Check className="mr-2 h-4 w-4" />
            Complete
          </Button>
        </div>
      </div>

      {/* Recording Area */}
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12">
          <RecordButton
            isRecording={isRecording}
            onStart={startRecording}
            onStop={stopRecording}
            disabled={transcribing}
          />
          <p className="mt-8 text-center text-sm text-muted-foreground max-w-sm">
            {transcribing
              ? "Processing..."
              : isRecording
              ? "Speak clearly: 'Six bottles of Tito\'s Vodka'"
              : "Tap to start recording"}
          </p>
        </CardContent>
      </Card>

      {/* Records List */}
      <div className="space-y-4">
        <h3 className="font-medium">Counts ({records?.length || 0})</h3>
        {records && records.length > 0 ? (
          <div className="space-y-2">
            {records.map((record) => (
              <CountRecordItem
                key={record.record_id}
                record={record}
                onConfirm={() => confirmRecord.mutate(record.record_id)}
                onEdit={() => setEditingRecord(record)}
                onDelete={() => {
                  // Delete not implemented in API yet
                  addToast({
                    title: "Delete not available",
                    variant: "destructive",
                  })
                }}
              />
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No counts recorded yet. Start recording to add items.
          </p>
        )}
      </div>

      <EditRecordDialog
        record={editingRecord}
        open={!!editingRecord}
        onOpenChange={(open) => !open && setEditingRecord(null)}
        onSave={(data) => {
          if (editingRecord) {
            updateRecord.mutate({ recordId: editingRecord.record_id, data })
          }
        }}
      />
    </div>
  )
}

export default function VoiceCountingPage() {
  const activeDatasetId = useAppStore((state) => state.activeDatasetId)

  return (
    <PageLayout title="Voice Count">
      {activeDatasetId ? (
        <VoiceCountingContent datasetId={activeDatasetId} />
      ) : (
        <EmptyState
          icon={<Package />}
          title="No dataset selected"
          description="Select a dataset from the dashboard to use voice counting."
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
