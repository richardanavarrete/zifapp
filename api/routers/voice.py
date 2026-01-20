"""
Voice Counting API Routes

Endpoints for transcription, matching, and session management.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends

from smallcogs.models.voice import (
    VoiceSession,
    CountRecord,
    TranscriptionResult,
    VoiceMatchRequest,
    VoiceMatchResponse,
    SessionExport,
    SessionStatus,
)
from smallcogs.services import VoiceService, InventoryService
from api.dependencies import get_voice_service, get_inventory_service

router = APIRouter(prefix="/voice", tags=["Voice Counting"])


# =============================================================================
# Sessions
# =============================================================================

@router.post("/sessions", response_model=VoiceSession)
async def create_session(
    name: str,
    dataset_id: Optional[str] = None,
    location: Optional[str] = None,
    voice_svc: VoiceService = Depends(get_voice_service),
):
    """Create a new voice counting session."""
    return voice_svc.create_session(name, dataset_id, location)


@router.get("/sessions", response_model=List[VoiceSession])
async def list_sessions(
    status: Optional[SessionStatus] = None,
    voice_svc: VoiceService = Depends(get_voice_service),
):
    """List all voice counting sessions."""
    return voice_svc.list_sessions(status)


@router.get("/sessions/{session_id}", response_model=VoiceSession)
async def get_session(
    session_id: str,
    voice_svc: VoiceService = Depends(get_voice_service),
):
    """Get a specific session."""
    session = voice_svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/sessions/{session_id}/complete", response_model=VoiceSession)
async def complete_session(
    session_id: str,
    voice_svc: VoiceService = Depends(get_voice_service),
):
    """Mark a session as completed."""
    session = voice_svc.complete_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# =============================================================================
# Transcription
# =============================================================================

@router.post("/transcribe", response_model=TranscriptionResult)
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str = Form(default="en"),
    voice_svc: VoiceService = Depends(get_voice_service),
):
    """
    Transcribe an audio file to text.

    Supports: webm, mp3, wav, m4a, ogg
    """
    # Save temp file
    import tempfile
    import os

    suffix = os.path.splitext(audio.filename)[1] if audio.filename else ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = await voice_svc.transcribe_audio(tmp_path, language)
        return result
    finally:
        os.unlink(tmp_path)


# =============================================================================
# Matching
# =============================================================================

@router.post("/match", response_model=VoiceMatchResponse)
async def match_text(
    request: VoiceMatchRequest,
    voice_svc: VoiceService = Depends(get_voice_service),
    inv_svc: InventoryService = Depends(get_inventory_service),
):
    """
    Parse voice text and match to inventory items.

    Input formats supported:
    - "buffalo trace 2 bottles"
    - "2 titos"
    - "jameson, 3"
    """
    dataset = None
    if request.dataset_id:
        dataset = inv_svc.get_dataset(request.dataset_id)

    return voice_svc.match_text(
        text=request.text,
        dataset=dataset,
        confidence_threshold=request.confidence_threshold,
        max_alternatives=request.max_alternatives,
    )


# =============================================================================
# Records
# =============================================================================

@router.post("/sessions/{session_id}/records", response_model=CountRecord)
async def add_record(
    session_id: str,
    raw_text: str,
    quantity: float,
    item_id: Optional[str] = None,
    item_name: Optional[str] = None,
    unit: str = "units",
    match_confidence: float = 0.0,
    voice_svc: VoiceService = Depends(get_voice_service),
):
    """Add a count record to a session."""
    record = voice_svc.add_record(
        session_id=session_id,
        raw_text=raw_text,
        item_id=item_id,
        item_name=item_name,
        quantity=quantity,
        unit=unit,
        match_confidence=match_confidence,
    )
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")
    return record


@router.get("/sessions/{session_id}/records", response_model=List[CountRecord])
async def get_records(
    session_id: str,
    voice_svc: VoiceService = Depends(get_voice_service),
):
    """Get all records for a session."""
    return voice_svc.get_records(session_id)


@router.post("/sessions/{session_id}/records/{record_id}/confirm")
async def confirm_record(
    session_id: str,
    record_id: str,
    voice_svc: VoiceService = Depends(get_voice_service),
):
    """Confirm a record as correct."""
    if not voice_svc.confirm_record(session_id, record_id):
        raise HTTPException(status_code=404, detail="Record not found")
    return {"status": "confirmed"}


@router.patch("/sessions/{session_id}/records/{record_id}", response_model=CountRecord)
async def update_record(
    session_id: str,
    record_id: str,
    item_name: Optional[str] = None,
    quantity: Optional[float] = None,
    voice_svc: VoiceService = Depends(get_voice_service),
):
    """Update a record (manual edit)."""
    record = voice_svc.update_record(session_id, record_id, item_name, quantity)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


# =============================================================================
# Export
# =============================================================================

@router.get("/sessions/{session_id}/export", response_model=SessionExport)
async def export_session(
    session_id: str,
    format: str = "csv",
    group_by_category: bool = False,
    voice_svc: VoiceService = Depends(get_voice_service),
):
    """
    Export session data for copy/paste.

    Returns CSV text and summary text ready for clipboard.
    """
    export = voice_svc.export_session(session_id, format, group_by_category)
    if not export:
        raise HTTPException(status_code=404, detail="Session not found")
    return export
