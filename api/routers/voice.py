"""Voice counting endpoints."""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Body, File, UploadFile, BackgroundTasks
from pydantic import BaseModel

from api.dependencies import get_api_key, get_file_storage
from api.middleware.errors import NotFoundError, ProcessingError
from houndcogs.models.voice import (
    VoiceSession,
    VoiceCountRecord,
    TranscriptionResult,
    VoiceMatchRequest,
    VoiceMatchResponse,
    SessionExport,
)
from houndcogs.models.common import SessionStatus

router = APIRouter()


class CreateSessionRequest(BaseModel):
    """Request to create a new voice counting session."""
    session_name: str
    location: Optional[str] = None
    notes: Optional[str] = None


class UpdateSessionRequest(BaseModel):
    """Request to update a session."""
    status: Optional[SessionStatus] = None
    notes: Optional[str] = None


class AddRecordRequest(BaseModel):
    """Request to add a count record to a session."""
    raw_text: str
    item_id: Optional[str] = None
    quantity: float
    unit: str = "bottles"
    confirmed: bool = False


@router.post("/sessions", response_model=VoiceSession)
async def create_session(
    request: CreateSessionRequest = Body(...),
    api_key: str = Depends(get_api_key),
):
    """
    Create a new voice counting session.

    A session groups count records for a single counting event
    (e.g., weekly inventory count for a specific location).
    """
    session_id = f"sess_{uuid.uuid4().hex[:12]}"

    session = VoiceSession(
        session_id=session_id,
        session_name=request.session_name,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        status=SessionStatus.IN_PROGRESS,
        location=request.location,
        notes=request.notes,
    )

    # TODO: Save to database
    # from houndcogs.storage.sqlite_repo import save_session
    # save_session(session)

    return session


@router.get("/sessions", response_model=List[VoiceSession])
async def list_sessions(
    status: Optional[SessionStatus] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    api_key: str = Depends(get_api_key),
):
    """
    List voice counting sessions.
    """
    # TODO: Implement with storage
    return []


@router.get("/sessions/{session_id}", response_model=VoiceSession)
async def get_session(
    session_id: str,
    api_key: str = Depends(get_api_key),
):
    """
    Get a specific session with its count records.
    """
    # TODO: Implement
    raise NotFoundError("Session", session_id)


@router.put("/sessions/{session_id}", response_model=VoiceSession)
async def update_session(
    session_id: str,
    request: UpdateSessionRequest = Body(...),
    api_key: str = Depends(get_api_key),
):
    """
    Update a session (status, notes).
    """
    # TODO: Implement
    raise NotFoundError("Session", session_id)


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    api_key: str = Depends(get_api_key),
):
    """
    Delete a session and all its records.
    """
    # TODO: Implement
    return {"status": "deleted", "session_id": session_id}


@router.post("/transcribe", response_model=TranscriptionResult)
async def transcribe_audio(
    file: UploadFile = File(..., description="Audio file (webm, mp3, wav, m4a)"),
    language: str = Query("en", description="Language code"),
    remove_silence: bool = Query(True, description="Remove silence from audio"),
    api_key: str = Depends(get_api_key),
    file_storage = Depends(get_file_storage),
    background_tasks: BackgroundTasks = None,
):
    """
    Transcribe an audio file to text.

    Uses OpenAI Whisper API for transcription. Long files are
    chunked and processed in parallel.

    **Supported formats**: webm, mp3, wav, m4a, ogg, flac

    **For long files (>30 minutes)**: Consider using background processing.
    """
    import time
    start_time = time.perf_counter()
    transcription_id = f"tr_{uuid.uuid4().hex[:12]}"

    # Validate file type
    valid_extensions = ('.webm', '.mp3', '.wav', '.m4a', '.ogg', '.flac')
    if not file.filename.lower().endswith(valid_extensions):
        raise ProcessingError(
            message=f"Invalid audio format. Supported: {', '.join(valid_extensions)}",
            details={"filename": file.filename}
        )

    try:
        # Save file temporarily
        file_path = await file_storage.save_temp(file, prefix=transcription_id)

        # TODO: Implement with houndcogs.services.audio_processor
        # from houndcogs.services.audio_processor import transcribe_audio_file
        # result = transcribe_audio_file(
        #     file_path=file_path,
        #     language=language,
        #     remove_silence=remove_silence
        # )

        processing_time = time.perf_counter() - start_time

        # Placeholder
        return TranscriptionResult(
            transcription_id=transcription_id,
            text="",  # Will be populated by transcriber
            duration_seconds=0.0,
            confidence=0.0,
            chunks_processed=1,
            processing_time_seconds=processing_time,
            warnings=["Transcription not yet implemented"]
        )

    except Exception as e:
        raise ProcessingError(
            message=f"Failed to transcribe audio: {str(e)}",
            details={"filename": file.filename}
        )


@router.post("/match", response_model=VoiceMatchResponse)
async def match_text_to_items(
    request: VoiceMatchRequest = Body(...),
    api_key: str = Depends(get_api_key),
):
    """
    Match transcribed text to inventory items.

    Parses the text to extract item names and quantities,
    then fuzzy-matches to inventory items.

    **Example input**: "buffalo trace 2 bottles titos 3 bottles"

    **Returns**: Matched items with confidence scores and alternatives.
    """
    import time
    start_time = time.perf_counter()

    try:
        # TODO: Implement with houndcogs.services.fuzzy_matcher
        # from houndcogs.services.fuzzy_matcher import match_voice_text
        # matches = match_voice_text(
        #     text=request.text,
        #     confidence_threshold=request.confidence_threshold,
        #     max_alternatives=request.max_alternatives
        # )

        processing_time = (time.perf_counter() - start_time) * 1000

        # Placeholder
        return VoiceMatchResponse(
            matches=[],
            unmatched=[request.text],
            processing_time_ms=processing_time
        )

    except Exception as e:
        raise ProcessingError(
            message=f"Failed to match text: {str(e)}"
        )


@router.post("/sessions/{session_id}/records", response_model=VoiceCountRecord)
async def add_record(
    session_id: str,
    request: AddRecordRequest = Body(...),
    api_key: str = Depends(get_api_key),
):
    """
    Add a count record to a session.

    Records can be added with or without a matched item_id.
    Unmatched records can be reviewed and matched later.
    """
    record_id = f"rec_{uuid.uuid4().hex[:12]}"

    record = VoiceCountRecord(
        record_id=record_id,
        session_id=session_id,
        created_at=datetime.utcnow(),
        raw_text=request.raw_text,
        item_id=request.item_id,
        quantity=request.quantity,
        unit=request.unit,
        confirmed=request.confirmed,
    )

    # TODO: Save to database
    return record


@router.get("/sessions/{session_id}/records", response_model=List[VoiceCountRecord])
async def list_records(
    session_id: str,
    confirmed_only: bool = Query(False, description="Only return confirmed records"),
    api_key: str = Depends(get_api_key),
):
    """
    List records in a session.
    """
    # TODO: Implement
    return []


@router.put("/sessions/{session_id}/records/{record_id}", response_model=VoiceCountRecord)
async def update_record(
    session_id: str,
    record_id: str,
    item_id: Optional[str] = Body(None),
    quantity: Optional[float] = Body(None),
    confirmed: Optional[bool] = Body(None),
    api_key: str = Depends(get_api_key),
):
    """
    Update a count record (correct item match, quantity, or confirm).
    """
    # TODO: Implement
    raise NotFoundError("Record", record_id)


@router.delete("/sessions/{session_id}/records/{record_id}")
async def delete_record(
    session_id: str,
    record_id: str,
    api_key: str = Depends(get_api_key),
):
    """
    Delete a count record.
    """
    return {"status": "deleted", "record_id": record_id}


@router.get("/sessions/{session_id}/export", response_model=SessionExport)
async def export_session(
    session_id: str,
    format: str = Query("json", description="Export format: json, csv"),
    api_key: str = Depends(get_api_key),
):
    """
    Export session data.

    Returns all confirmed records with summaries by category.
    """
    # TODO: Implement
    raise NotFoundError("Session", session_id)
