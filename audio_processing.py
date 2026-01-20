"""
Audio Processing Module - Silence removal and chunking for voice counting.

This module provides:
- Silence removal from audio recordings
- Chunking audio into 30-second segments with 1-second overlaps
- OpenAI Whisper API transcription for chunked audio
"""

import io
import tempfile
import os
from typing import List, Tuple, Optional
from pydub import AudioSegment
from pydub.silence import detect_nonsilent


def remove_silence(audio: AudioSegment,
                   min_silence_len: int = 500,
                   silence_thresh: int = -40,
                   keep_silence: int = 200) -> AudioSegment:
    """
    Remove silence from audio while keeping natural pauses.

    Args:
        audio: AudioSegment to process
        min_silence_len: Minimum length of silence to detect (ms)
        silence_thresh: Silence threshold in dBFS (default -40)
        keep_silence: Amount of silence to keep at edges (ms)

    Returns:
        AudioSegment with silences removed
    """
    # Detect non-silent chunks
    nonsilent_ranges = detect_nonsilent(
        audio,
        min_silence_len=min_silence_len,
        silence_thresh=silence_thresh
    )

    if not nonsilent_ranges:
        # No speech detected, return original
        return audio

    # Combine non-silent chunks with small gaps
    chunks = []
    for start, end in nonsilent_ranges:
        # Add a bit of padding around each chunk for natural speech
        chunk_start = max(0, start - keep_silence)
        chunk_end = min(len(audio), end + keep_silence)
        chunks.append(audio[chunk_start:chunk_end])

    # Join chunks with small silence gap
    if chunks:
        result = chunks[0]
        silence_gap = AudioSegment.silent(duration=100)  # 100ms gap between phrases
        for chunk in chunks[1:]:
            result = result + silence_gap + chunk
        return result

    return audio


def chunk_audio(audio: AudioSegment,
                chunk_duration_ms: int = 30000,
                overlap_ms: int = 1000) -> List[AudioSegment]:
    """
    Split audio into chunks with overlap for better transcription.

    Args:
        audio: AudioSegment to chunk
        chunk_duration_ms: Duration of each chunk in milliseconds (default 30s)
        overlap_ms: Overlap between chunks in milliseconds (default 1s)

    Returns:
        List of AudioSegment chunks
    """
    chunks = []
    audio_len = len(audio)

    if audio_len <= chunk_duration_ms:
        # Audio is shorter than chunk size, return as single chunk
        return [audio]

    start = 0
    step = chunk_duration_ms - overlap_ms  # Step size accounts for overlap

    while start < audio_len:
        end = min(start + chunk_duration_ms, audio_len)
        chunk = audio[start:end]

        # Only add chunks that have meaningful content (> 500ms)
        if len(chunk) > 500:
            chunks.append(chunk)

        # Move to next chunk position
        start += step

        # Stop if we've processed all audio
        if end >= audio_len:
            break

    return chunks


def process_audio_for_transcription(audio: AudioSegment) -> List[AudioSegment]:
    """
    Process audio: remove silence and chunk into 30s segments with 1s overlap.

    Args:
        audio: Raw AudioSegment from recording

    Returns:
        List of processed AudioSegment chunks ready for transcription
    """
    # Step 1: Remove silence
    cleaned_audio = remove_silence(audio)

    # Step 2: Chunk into 30s segments with 1s overlap
    chunks = chunk_audio(cleaned_audio, chunk_duration_ms=30000, overlap_ms=1000)

    return chunks


def audio_to_bytes(audio: AudioSegment, format: str = "wav") -> bytes:
    """Convert AudioSegment to bytes."""
    buffer = io.BytesIO()
    audio.export(buffer, format=format)
    buffer.seek(0)
    return buffer.read()


def transcribe_with_openai_api(audio_chunks: List[AudioSegment],
                                api_key: str) -> str:
    """
    Transcribe audio chunks using OpenAI's Whisper API.

    Args:
        audio_chunks: List of AudioSegment chunks
        api_key: OpenAI API key

    Returns:
        Combined transcription from all chunks
    """
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    transcriptions = []

    for i, chunk in enumerate(audio_chunks):
        # Save chunk to temporary file (OpenAI API needs a file)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            chunk.export(temp_file.name, format="wav")
            temp_path = temp_file.name

        try:
            # Call OpenAI Whisper API
            with open(temp_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en",
                    response_format="text"
                )

            if transcript:
                transcriptions.append(transcript.strip())
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    # Combine transcriptions, handling overlaps
    return merge_overlapping_transcriptions(transcriptions)


def merge_overlapping_transcriptions(transcriptions: List[str]) -> str:
    """
    Merge transcriptions from overlapping audio chunks.

    Since chunks have 1s overlap, there may be duplicate words at boundaries.
    This function attempts to merge them intelligently.

    Args:
        transcriptions: List of transcription strings from sequential chunks

    Returns:
        Merged transcription
    """
    if not transcriptions:
        return ""

    if len(transcriptions) == 1:
        return transcriptions[0]

    result = transcriptions[0]

    for i in range(1, len(transcriptions)):
        current = transcriptions[i]

        if not current:
            continue

        # Try to find overlap between end of result and start of current
        # Look for common word sequences (2-4 words)
        result_words = result.split()
        current_words = current.split()

        if not result_words or not current_words:
            result += " " + current
            continue

        # Check for overlap in last 4 words of result vs first 4 words of current
        overlap_found = False
        for overlap_len in range(min(4, len(result_words), len(current_words)), 0, -1):
            # Compare last N words of result with first N words of current
            result_end = " ".join(result_words[-overlap_len:]).lower()
            current_start = " ".join(current_words[:overlap_len]).lower()

            if result_end == current_start:
                # Found overlap, merge without duplication
                result = " ".join(result_words) + " " + " ".join(current_words[overlap_len:])
                overlap_found = True
                break

        if not overlap_found:
            # No overlap found, just concatenate with space
            result = result + " " + current

    return result.strip()


def get_audio_duration_seconds(audio: AudioSegment) -> float:
    """Get audio duration in seconds."""
    return len(audio) / 1000.0


def get_chunk_info(audio: AudioSegment,
                   chunk_duration_ms: int = 30000,
                   overlap_ms: int = 1000) -> Tuple[int, float]:
    """
    Get information about how audio will be chunked.

    Args:
        audio: AudioSegment to analyze
        chunk_duration_ms: Chunk duration in ms
        overlap_ms: Overlap in ms

    Returns:
        Tuple of (num_chunks, total_duration_seconds)
    """
    # First remove silence to get accurate estimate
    cleaned = remove_silence(audio)
    chunks = chunk_audio(cleaned, chunk_duration_ms, overlap_ms)
    return len(chunks), get_audio_duration_seconds(cleaned)
