"""
Voice Counting Models

For transcribing audio, matching to inventory items, and exporting counts.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    """Voice session status."""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class VoiceSession(BaseModel):
    """A voice counting session."""
    session_id: str
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: SessionStatus = SessionStatus.IN_PROGRESS

    # Optional context
    dataset_id: Optional[str] = Field(default=None, description="Link to inventory dataset for matching")
    location: Optional[str] = Field(default=None, description="Physical location being counted")
    notes: Optional[str] = None

    # Stats
    items_counted: int = 0
    total_units: float = 0.0


class CountRecord(BaseModel):
    """A single counted item from voice input."""
    record_id: str
    session_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Raw input
    raw_text: str = Field(..., description="Original transcribed text segment")

    # Parsed/matched data
    item_id: Optional[str] = Field(default=None, description="Matched item ID from dataset")
    item_name: Optional[str] = Field(default=None, description="Matched or manually entered item name")
    quantity: float = Field(..., ge=0)
    unit: str = Field(default="units", description="bottles, cases, each, etc.")

    # Match quality
    match_confidence: float = Field(default=0.0, ge=0, le=1)
    match_method: Optional[str] = Field(default=None, description="exact, fuzzy, manual")

    # User actions
    confirmed: bool = False
    manually_edited: bool = False


class TranscriptionResult(BaseModel):
    """Result from audio transcription."""
    transcription_id: str
    text: str
    duration_seconds: float

    # Quality
    confidence: float = Field(default=0.0, ge=0, le=1)
    language: str = "en"

    # Processing info
    chunks_processed: int = 1
    processing_time_ms: float = 0.0

    # Issues
    warnings: List[str] = Field(default_factory=list)


class MatchCandidate(BaseModel):
    """A potential match for voice input."""
    item_id: str
    item_name: str
    category: Optional[str] = None
    confidence: float = Field(..., ge=0, le=1)
    match_method: str  # exact, fuzzy, partial, phonetic


class ParsedVoiceInput(BaseModel):
    """Parsed structure from voice text."""
    raw_text: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    item_text: Optional[str] = Field(default=None, description="The item name portion")

    # Best match
    best_match: Optional[MatchCandidate] = None
    alternatives: List[MatchCandidate] = Field(default_factory=list)

    # Status
    needs_review: bool = False
    parse_confidence: float = 0.0


class VoiceMatchRequest(BaseModel):
    """Request to match voice text against inventory."""
    text: str
    dataset_id: Optional[str] = Field(default=None, description="Dataset to match against")
    session_id: Optional[str] = None
    confidence_threshold: float = Field(default=0.7, ge=0, le=1)
    max_alternatives: int = Field(default=3, ge=0, le=10)


class VoiceMatchResponse(BaseModel):
    """Response from voice matching."""
    parsed_items: List[ParsedVoiceInput]
    unmatched_text: List[str] = Field(default_factory=list)
    processing_time_ms: float = 0.0


class SessionExport(BaseModel):
    """Exported session data for copy/paste."""
    session_id: str
    session_name: str
    exported_at: datetime = Field(default_factory=datetime.utcnow)

    # Counts
    records: List[CountRecord]
    total_items: int
    total_units: float

    # Grouped data
    by_category: Dict[str, List[CountRecord]] = Field(default_factory=dict)

    # Export formats
    csv_text: Optional[str] = Field(default=None, description="CSV formatted for copy/paste")
    summary_text: Optional[str] = Field(default=None, description="Human-readable summary")


class TranscribeRequest(BaseModel):
    """Configuration for transcription request."""
    language: str = "en"
    remove_silence: bool = True
    chunk_duration_seconds: int = Field(default=30, ge=10, le=120)
