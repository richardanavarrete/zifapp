"""
Audio Processor

Handles audio transcription using OpenAI Whisper API.
Supports long recordings with chunking and parallel processing.
"""

import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional

from houndcogs.models.voice import TranscriptionResult

logger = logging.getLogger(__name__)


# Maximum chunk duration in seconds
MAX_CHUNK_DURATION = 30

# Overlap between chunks in seconds (to avoid cutting words)
CHUNK_OVERLAP = 1


def transcribe_audio(
    file_path: str,
    language: str = "en",
    remove_silence: bool = True,
    api_key: Optional[str] = None,
) -> TranscriptionResult:
    """
    Transcribe an audio file to text using OpenAI Whisper API.

    Args:
        file_path: Path to audio file
        language: Language code (default: en)
        remove_silence: Whether to remove silence before processing
        api_key: OpenAI API key (uses OPENAI_API_KEY env var if not provided)

    Returns:
        TranscriptionResult with transcribed text
    """
    import time
    start_time = time.perf_counter()

    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API key required for transcription")

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    # Get audio duration
    duration = _get_audio_duration(file_path)
    logger.info(f"Processing audio file: {duration:.1f}s")

    warnings = []

    # Process audio
    if remove_silence:
        try:
            processed_path = _remove_silence(file_path)
            new_duration = _get_audio_duration(processed_path)
            if new_duration < duration * 0.9:
                logger.info(f"Removed silence: {duration:.1f}s -> {new_duration:.1f}s")
            file_path = processed_path
            duration = new_duration
        except Exception as e:
            warnings.append(f"Failed to remove silence: {e}")

    # Chunk if longer than threshold
    if duration > MAX_CHUNK_DURATION * 2:
        chunks = _split_audio(file_path, MAX_CHUNK_DURATION, CHUNK_OVERLAP)
        logger.info(f"Split into {len(chunks)} chunks")
    else:
        chunks = [file_path]

    # Transcribe chunks (in parallel if multiple)
    transcriptions = _transcribe_chunks(chunks, language, api_key)

    # Combine results
    full_text = " ".join(transcriptions)

    # Clean up temp files
    for chunk in chunks:
        if chunk != file_path and os.path.exists(chunk):
            try:
                os.remove(chunk)
            except Exception:
                pass

    processing_time = time.perf_counter() - start_time

    return TranscriptionResult(
        transcription_id=f"tr_{os.urandom(6).hex()}",
        text=full_text.strip(),
        duration_seconds=duration,
        confidence=0.9,  # Whisper doesn't return confidence
        chunks_processed=len(chunks),
        processing_time_seconds=processing_time,
        warnings=warnings,
    )


def _get_audio_duration(file_path: str) -> float:
    """Get audio file duration in seconds."""
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(file_path)
        return len(audio) / 1000.0
    except Exception:
        # Fallback: estimate from file size
        size = os.path.getsize(file_path)
        return size / 16000  # Rough estimate for 16kHz audio


def _remove_silence(file_path: str) -> str:
    """Remove silence from audio file."""
    from pydub import AudioSegment
    from pydub.silence import detect_nonsilent

    audio = AudioSegment.from_file(file_path)

    # Detect non-silent chunks
    nonsilent_ranges = detect_nonsilent(
        audio,
        min_silence_len=500,  # 500ms
        silence_thresh=-40,    # dB
    )

    if not nonsilent_ranges:
        return file_path

    # Combine non-silent parts with small padding
    combined = AudioSegment.empty()
    for start, end in nonsilent_ranges:
        # Add small padding
        start = max(0, start - 100)
        end = min(len(audio), end + 100)
        combined += audio[start:end]

    # Export to temp file
    output_path = tempfile.mktemp(suffix=".wav")
    combined.export(output_path, format="wav")

    return output_path


def _split_audio(
    file_path: str,
    chunk_duration: int,
    overlap: int,
) -> List[str]:
    """Split audio file into chunks."""
    from pydub import AudioSegment

    audio = AudioSegment.from_file(file_path)
    duration_ms = len(audio)
    chunk_ms = chunk_duration * 1000
    overlap_ms = overlap * 1000

    chunks = []
    start = 0

    while start < duration_ms:
        end = min(start + chunk_ms, duration_ms)
        chunk = audio[start:end]

        # Export chunk
        chunk_path = tempfile.mktemp(suffix=".wav")
        chunk.export(chunk_path, format="wav")
        chunks.append(chunk_path)

        # Move start, accounting for overlap
        start = end - overlap_ms
        if start >= duration_ms - overlap_ms:
            break

    return chunks


def _transcribe_chunks(
    chunk_paths: List[str],
    language: str,
    api_key: str,
) -> List[str]:
    """Transcribe multiple chunks, potentially in parallel."""
    if len(chunk_paths) == 1:
        return [_transcribe_single(chunk_paths[0], language, api_key)]

    # Parallel transcription
    results = [""] * len(chunk_paths)

    with ThreadPoolExecutor(max_workers=min(4, len(chunk_paths))) as executor:
        future_to_idx = {
            executor.submit(_transcribe_single, path, language, api_key): idx
            for idx, path in enumerate(chunk_paths)
        }

        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                logger.error(f"Chunk {idx} failed: {e}")
                results[idx] = ""

    return results


def _transcribe_single(
    file_path: str,
    language: str,
    api_key: str,
) -> str:
    """Transcribe a single audio file using OpenAI Whisper API."""
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        with open(file_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=language,
                response_format="text",
            )

        return response.strip() if isinstance(response, str) else response.text.strip()

    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise
