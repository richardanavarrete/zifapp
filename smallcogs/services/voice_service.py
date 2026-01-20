"""
Voice Counting Service

Handles audio transcription, item matching, and export for copy/paste.
"""

import logging
import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from smallcogs.models.inventory import Dataset
from smallcogs.models.voice import (
    CountRecord,
    MatchCandidate,
    ParsedVoiceInput,
    SessionExport,
    SessionStatus,
    TranscriptionResult,
    VoiceMatchResponse,
    VoiceSession,
)

logger = logging.getLogger(__name__)


class VoiceService:
    """Service for voice-based inventory counting."""

    def __init__(self, openai_api_key: Optional[str] = None):
        self.openai_api_key = openai_api_key
        self._sessions: Dict[str, VoiceSession] = {}
        self._records: Dict[str, List[CountRecord]] = {}  # session_id -> records

    # =========================================================================
    # Session Management
    # =========================================================================

    def create_session(
        self,
        name: str,
        dataset_id: Optional[str] = None,
        location: Optional[str] = None,
    ) -> VoiceSession:
        """Create a new counting session."""
        session = VoiceSession(
            session_id=f"vs_{uuid.uuid4().hex[:12]}",
            name=name,
            dataset_id=dataset_id,
            location=location,
        )
        self._sessions[session.session_id] = session
        self._records[session.session_id] = []
        return session

    def get_session(self, session_id: str) -> Optional[VoiceSession]:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def list_sessions(self, status: Optional[SessionStatus] = None) -> List[VoiceSession]:
        """List all sessions, optionally filtered by status."""
        sessions = list(self._sessions.values())
        if status:
            sessions = [s for s in sessions if s.status == status]
        return sorted(sessions, key=lambda s: s.created_at, reverse=True)

    def complete_session(self, session_id: str) -> Optional[VoiceSession]:
        """Mark a session as completed."""
        session = self._sessions.get(session_id)
        if session:
            session.status = SessionStatus.COMPLETED
            session.updated_at = datetime.utcnow()
        return session

    # =========================================================================
    # Transcription
    # =========================================================================

    async def transcribe_audio(
        self,
        audio_path: str,
        language: str = "en",
        remove_silence: bool = True,
    ) -> TranscriptionResult:
        """
        Transcribe audio file to text.

        Uses OpenAI Whisper API if available, otherwise falls back to local.
        """
        import time
        start = time.time()

        transcription_id = f"tr_{uuid.uuid4().hex[:12]}"

        # Try OpenAI Whisper API
        if self.openai_api_key:
            text, confidence = await self._transcribe_openai(audio_path, language)
        else:
            # Fallback - would use local whisper or speech_recognition
            text, confidence = await self._transcribe_fallback(audio_path)

        processing_time = (time.time() - start) * 1000

        return TranscriptionResult(
            transcription_id=transcription_id,
            text=text,
            duration_seconds=0.0,  # TODO: get from audio file
            confidence=confidence,
            language=language,
            processing_time_ms=processing_time,
        )

    async def _transcribe_openai(
        self,
        audio_path: str,
        language: str
    ) -> Tuple[str, float]:
        """Transcribe using OpenAI Whisper API."""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.openai_api_key)

            with open(audio_path, "rb") as audio_file:
                response = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language,
                )

            return response.text, 0.9  # Whisper doesn't return confidence
        except Exception as e:
            logger.error(f"OpenAI transcription failed: {e}")
            return "", 0.0

    async def _transcribe_fallback(self, audio_path: str) -> Tuple[str, float]:
        """Fallback transcription using local methods."""
        # Placeholder - would use speech_recognition or local whisper
        logger.warning("No OpenAI key - using fallback transcription")
        return "", 0.0

    # =========================================================================
    # Matching
    # =========================================================================

    def match_text(
        self,
        text: str,
        dataset: Optional[Dataset] = None,
        confidence_threshold: float = 0.7,
        max_alternatives: int = 3,
    ) -> VoiceMatchResponse:
        """
        Parse voice text and match to inventory items.

        Expected input formats:
        - "buffalo trace 2 bottles"
        - "2 titos"
        - "jameson, 3"
        """
        import time
        start = time.time()

        # Split into segments (by comma, "and", newline)
        segments = self._split_segments(text)

        parsed_items = []
        unmatched = []

        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue

            parsed = self._parse_segment(segment)

            if dataset and parsed.item_text:
                # Try to match against inventory
                matches = self._find_matches(
                    parsed.item_text,
                    dataset,
                    max_results=max_alternatives + 1
                )

                if matches and matches[0].confidence >= confidence_threshold:
                    parsed.best_match = matches[0]
                    parsed.alternatives = matches[1:max_alternatives + 1]
                    parsed.parse_confidence = matches[0].confidence
                else:
                    parsed.needs_review = True
                    parsed.alternatives = matches[:max_alternatives]
            else:
                parsed.needs_review = True

            if parsed.item_text:
                parsed_items.append(parsed)
            else:
                unmatched.append(segment)

        processing_time = (time.time() - start) * 1000

        return VoiceMatchResponse(
            parsed_items=parsed_items,
            unmatched_text=unmatched,
            processing_time_ms=processing_time,
        )

    def _split_segments(self, text: str) -> List[str]:
        """Split text into countable segments."""
        # Split on common delimiters
        text = text.replace("\n", ",")
        text = re.sub(r"\band\b", ",", text, flags=re.IGNORECASE)
        return [s.strip() for s in text.split(",") if s.strip()]

    def _parse_segment(self, segment: str) -> ParsedVoiceInput:
        """Parse a segment into quantity, unit, and item name."""
        segment = segment.strip().lower()

        # Patterns: "2 bottles buffalo trace", "buffalo trace 2", "buffalo trace 2 bottles"
        patterns = [
            # "2 bottles of buffalo trace"
            r"^(\d+(?:\.\d+)?)\s*(bottles?|cases?|units?|each)?\s*(?:of\s+)?(.+)$",
            # "buffalo trace 2 bottles"
            r"^(.+?)\s+(\d+(?:\.\d+)?)\s*(bottles?|cases?|units?|each)?$",
            # "buffalo trace, 2"
            r"^(.+?),?\s+(\d+(?:\.\d+)?)$",
        ]

        for pattern in patterns:
            match = re.match(pattern, segment, re.IGNORECASE)
            if match:
                groups = match.groups()

                # Determine which group is quantity vs item
                if groups[0] and re.match(r"^\d", groups[0]):
                    qty = float(groups[0])
                    unit = groups[1] or "units"
                    item = groups[2] if len(groups) > 2 else ""
                else:
                    item = groups[0]
                    qty = float(groups[1]) if groups[1] else 1.0
                    unit = groups[2] if len(groups) > 2 and groups[2] else "units"

                return ParsedVoiceInput(
                    raw_text=segment,
                    quantity=qty,
                    unit=unit.rstrip("s"),  # Normalize to singular
                    item_text=item.strip() if item else None,
                )

        # No pattern matched - treat whole thing as item name
        return ParsedVoiceInput(
            raw_text=segment,
            quantity=1.0,
            unit="unit",
            item_text=segment,
            needs_review=True,
        )

    def _find_matches(
        self,
        search_text: str,
        dataset: Dataset,
        max_results: int = 5
    ) -> List[MatchCandidate]:
        """Find matching items in dataset using fuzzy matching."""
        try:
            from rapidfuzz import fuzz, process
        except ImportError:
            logger.warning("rapidfuzz not installed - using basic matching")
            return self._basic_match(search_text, dataset, max_results)

        search_lower = search_text.lower()
        candidates = []

        # Build choices dict
        choices = {item.item_id: item.name.lower() for item in dataset.items.values()}

        # Use rapidfuzz to find matches
        results = process.extract(
            search_lower,
            choices,
            scorer=fuzz.WRatio,
            limit=max_results
        )

        for name, score, item_id in results:
            item = dataset.items[item_id]
            candidates.append(MatchCandidate(
                item_id=item_id,
                item_name=item.name,
                category=item.category,
                confidence=score / 100.0,
                match_method="fuzzy" if score < 100 else "exact",
            ))

        return candidates

    def _basic_match(
        self,
        search_text: str,
        dataset: Dataset,
        max_results: int
    ) -> List[MatchCandidate]:
        """Basic substring matching fallback."""
        search_lower = search_text.lower()
        matches = []

        for item in dataset.items.values():
            name_lower = item.name.lower()
            if search_lower in name_lower or name_lower in search_lower:
                # Simple similarity based on length ratio
                similarity = min(len(search_lower), len(name_lower)) / max(len(search_lower), len(name_lower))
                matches.append(MatchCandidate(
                    item_id=item.item_id,
                    item_name=item.name,
                    category=item.category,
                    confidence=similarity,
                    match_method="partial",
                ))

        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches[:max_results]

    # =========================================================================
    # Records
    # =========================================================================

    def add_record(
        self,
        session_id: str,
        raw_text: str,
        item_id: Optional[str] = None,
        item_name: Optional[str] = None,
        quantity: float = 1.0,
        unit: str = "units",
        match_confidence: float = 0.0,
    ) -> Optional[CountRecord]:
        """Add a count record to a session."""
        if session_id not in self._sessions:
            return None

        record = CountRecord(
            record_id=f"cr_{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            raw_text=raw_text,
            item_id=item_id,
            item_name=item_name,
            quantity=quantity,
            unit=unit,
            match_confidence=match_confidence,
        )

        self._records[session_id].append(record)

        # Update session stats
        session = self._sessions[session_id]
        session.items_counted += 1
        session.total_units += quantity
        session.updated_at = datetime.utcnow()

        return record

    def get_records(self, session_id: str) -> List[CountRecord]:
        """Get all records for a session."""
        return self._records.get(session_id, [])

    def confirm_record(self, session_id: str, record_id: str) -> bool:
        """Mark a record as confirmed."""
        records = self._records.get(session_id, [])
        for record in records:
            if record.record_id == record_id:
                record.confirmed = True
                return True
        return False

    def update_record(
        self,
        session_id: str,
        record_id: str,
        item_name: Optional[str] = None,
        quantity: Optional[float] = None,
    ) -> Optional[CountRecord]:
        """Update a record (manual edit)."""
        records = self._records.get(session_id, [])
        for record in records:
            if record.record_id == record_id:
                if item_name:
                    record.item_name = item_name
                if quantity is not None:
                    record.quantity = quantity
                record.manually_edited = True
                return record
        return None

    # =========================================================================
    # Export
    # =========================================================================

    def export_session(
        self,
        session_id: str,
        format: str = "csv",
        group_by_category: bool = False,
    ) -> Optional[SessionExport]:
        """Export session data for copy/paste."""
        session = self._sessions.get(session_id)
        if not session:
            return None

        records = self._records.get(session_id, [])

        # Group by category if requested
        by_category: Dict[str, List[CountRecord]] = {}
        if group_by_category:
            for record in records:
                cat = "Uncategorized"  # Would get from matched item
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(record)

        # Generate CSV text
        csv_lines = ["Item,Quantity,Unit"]
        for record in records:
            name = record.item_name or record.raw_text
            csv_lines.append(f"{name},{record.quantity},{record.unit}")
        csv_text = "\n".join(csv_lines)

        # Generate summary text
        summary_lines = [
            f"Session: {session.name}",
            f"Date: {session.created_at.strftime('%Y-%m-%d %H:%M')}",
            f"Items: {len(records)}",
            f"Total Units: {session.total_units}",
            "",
            "Counts:",
        ]
        for record in records:
            name = record.item_name or record.raw_text
            summary_lines.append(f"  {name}: {record.quantity} {record.unit}")
        summary_text = "\n".join(summary_lines)

        return SessionExport(
            session_id=session_id,
            session_name=session.name,
            records=records,
            total_items=len(records),
            total_units=session.total_units,
            by_category=by_category,
            csv_text=csv_text,
            summary_text=summary_text,
        )
