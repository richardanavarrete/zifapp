"""Voice counting data models."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from houndcogs.models.common import SessionStatus


class VoiceSession(BaseModel):
    """A voice counting session."""

    session_id: str
    session_name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: SessionStatus = Field(default=SessionStatus.IN_PROGRESS)

    # Metadata
    location: Optional[str] = Field(default=None, description="Physical location being counted")
    notes: Optional[str] = None

    # Statistics
    items_counted: int = 0
    total_units: float = 0.0


class VoiceCountRecord(BaseModel):
    """A single voice count entry."""

    record_id: str
    session_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Raw input
    raw_text: str = Field(..., description="Original transcribed text")

    # Matched item
    item_id: Optional[str] = None
    display_name: Optional[str] = None
    match_confidence: float = Field(default=0.0, ge=0, le=1)

    # Count
    quantity: float
    unit: str = Field(default="bottles")

    # Status
    confirmed: bool = Field(default=False, description="User confirmed the match")
    rejected: bool = Field(default=False, description="User rejected the match")
    manually_corrected: bool = Field(default=False)


class TranscriptionResult(BaseModel):
    """Result of transcribing audio."""

    transcription_id: str
    text: str
    duration_seconds: float
    confidence: float = Field(default=0.0, ge=0, le=1)

    # Processing info
    chunks_processed: int = 1
    processing_time_seconds: float = 0.0

    # Warnings
    warnings: List[str] = Field(default_factory=list)


class MatchCandidate(BaseModel):
    """A potential match for a voice input."""

    item_id: str
    display_name: str
    category: str
    confidence: float = Field(..., ge=0, le=1)
    match_method: str = Field(..., description="exact, fuzzy, partial, token_sort")


class MatchResult(BaseModel):
    """Result of matching transcribed text to inventory items."""

    raw_text: str
    parsed_quantity: Optional[float] = None
    parsed_unit: Optional[str] = None

    # Best match
    matched_item: Optional[MatchCandidate] = None

    # Alternative matches
    alternatives: List[MatchCandidate] = Field(default_factory=list)

    # Status
    is_confident_match: bool = Field(default=False, description="Confidence > threshold")
    needs_review: bool = Field(default=False)


class VoiceMatchRequest(BaseModel):
    """Request to match voice text to items."""

    text: str
    session_id: Optional[str] = None
    confidence_threshold: float = Field(default=0.8, ge=0, le=1)
    max_alternatives: int = Field(default=3, ge=0, le=10)


class VoiceMatchResponse(BaseModel):
    """Response from voice matching."""

    matches: List[MatchResult]
    unmatched: List[str] = Field(default_factory=list)
    processing_time_ms: float = 0.0


class TranscribeRequest(BaseModel):
    """Request configuration for transcription."""

    # Audio is sent as file upload, not in JSON body
    language: str = Field(default="en")
    chunk_duration_seconds: int = Field(default=30, ge=10, le=60)
    remove_silence: bool = Field(default=True)


class SessionExport(BaseModel):
    """Exported session data."""

    session_id: str
    session_name: str
    created_at: datetime
    status: str

    records: List[VoiceCountRecord]

    # Summary
    total_items: int
    total_units: float
    confirmed_count: int
    unconfirmed_count: int

    # Grouped by category
    by_category: Dict[str, float] = Field(default_factory=dict)
