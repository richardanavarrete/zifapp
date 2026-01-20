"""
Audio Processing Module - Optimized silence removal and chunking for voice counting.

This module provides:
- Fast silence removal from audio recordings
- Chunking audio into 30-second segments with 1-second overlaps
- Parallel OpenAI Whisper API transcription for speed
"""

import io
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple

from pydub import AudioSegment
from pydub.silence import detect_nonsilent


def normalize_audio(audio: AudioSegment, target_dbfs: float = -20.0) -> AudioSegment:
    """Normalize audio to target dBFS for consistent levels."""
    change_in_dbfs = target_dbfs - audio.dBFS
    return audio.apply_gain(change_in_dbfs)


def remove_silence(audio: AudioSegment,
                   min_silence_len: int = 400,
                   silence_thresh: int = -45,
                   keep_silence: int = 150) -> AudioSegment:
    """
    Remove silence from audio while keeping natural pauses.
    Optimized parameters for voice recordings.

    Args:
        audio: AudioSegment to process
        min_silence_len: Minimum length of silence to detect (ms) - reduced for faster detection
        silence_thresh: Silence threshold in dBFS - more sensitive for voice
        keep_silence: Amount of silence to keep at edges (ms)

    Returns:
        AudioSegment with silences removed
    """
    # Normalize audio first for better silence detection
    normalized = normalize_audio(audio)

    # Detect non-silent chunks
    nonsilent_ranges = detect_nonsilent(
        normalized,
        min_silence_len=min_silence_len,
        silence_thresh=silence_thresh
    )

    if not nonsilent_ranges:
        # No speech detected, return original
        return audio

    # Combine non-silent chunks with small gaps
    chunks = []
    for start, end in nonsilent_ranges:
        # Add padding around each chunk for natural speech
        chunk_start = max(0, start - keep_silence)
        chunk_end = min(len(audio), end + keep_silence)
        chunks.append(audio[chunk_start:chunk_end])

    # Join chunks with small silence gap
    if chunks:
        result = chunks[0]
        silence_gap = AudioSegment.silent(duration=80)  # 80ms gap between phrases
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
    step = chunk_duration_ms - overlap_ms

    while start < audio_len:
        end = min(start + chunk_duration_ms, audio_len)
        chunk = audio[start:end]

        # Only add chunks that have meaningful content (> 500ms)
        if len(chunk) > 500:
            chunks.append(chunk)

        start += step

        if end >= audio_len:
            break

    return chunks


def process_audio_for_transcription(audio: AudioSegment) -> List[AudioSegment]:
    """
    Process audio: remove silence and chunk into segments.
    Automatically adjusts chunk size based on audio length.

    Args:
        audio: Raw AudioSegment from recording

    Returns:
        List of processed AudioSegment chunks ready for transcription
    """
    audio_len = len(audio)

    # For short audio (< 25s), skip silence removal - just send directly
    if audio_len < 25000:
        return [audio]

    # Step 1: Remove silence
    cleaned_audio = remove_silence(audio)

    # Step 2: Choose chunk size based on audio length
    # Longer audio = larger chunks to reduce API calls
    cleaned_len = len(cleaned_audio)
    if cleaned_len > 300000:  # > 5 minutes
        # Use 60-second chunks with 2s overlap for very long audio
        chunk_duration = 60000
        overlap = 2000
    elif cleaned_len > 120000:  # > 2 minutes
        # Use 45-second chunks with 1.5s overlap
        chunk_duration = 45000
        overlap = 1500
    else:
        # Standard 30-second chunks with 1s overlap
        chunk_duration = 30000
        overlap = 1000

    chunks = chunk_audio(cleaned_audio, chunk_duration_ms=chunk_duration, overlap_ms=overlap)

    return chunks


def _transcribe_single_chunk(args: Tuple[int, AudioSegment, str]) -> Tuple[int, str]:
    """
    Transcribe a single audio chunk. Used for parallel processing.

    Args:
        args: Tuple of (chunk_index, audio_chunk, api_key)

    Returns:
        Tuple of (chunk_index, transcription)
    """
    from openai import OpenAI

    chunk_index, chunk, api_key = args
    client = OpenAI(api_key=api_key)

    # Use MP3 format - much smaller files = faster upload
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        chunk.export(temp_file.name, format="mp3", bitrate="64k")
        temp_path = temp_file.name

    try:
        with open(temp_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="en",
                response_format="text"
            )
        return (chunk_index, transcript.strip() if transcript else "")
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def transcribe_with_openai_api(audio_chunks: List[AudioSegment],
                                api_key: str,
                                max_workers: int = None,
                                progress_callback=None) -> str:
    """
    Transcribe audio chunks using OpenAI's Whisper API in parallel.

    Args:
        audio_chunks: List of AudioSegment chunks
        api_key: OpenAI API key
        max_workers: Maximum parallel API calls (auto-scales based on chunk count if None)
        progress_callback: Optional callback(completed, total) for progress updates

    Returns:
        Combined transcription from all chunks
    """
    if not audio_chunks:
        return ""

    # Single chunk - no need for parallel processing
    if len(audio_chunks) == 1:
        _, transcript = _transcribe_single_chunk((0, audio_chunks[0], api_key))
        return transcript

    # Auto-scale workers based on chunk count (more chunks = more parallelism)
    if max_workers is None:
        if len(audio_chunks) > 20:
            max_workers = 10  # Many chunks - max parallelism
        elif len(audio_chunks) > 10:
            max_workers = 8
        elif len(audio_chunks) > 5:
            max_workers = 6
        else:
            max_workers = 4

    # Multiple chunks - process in parallel
    transcriptions = [""] * len(audio_chunks)
    completed = 0

    # Prepare args for each chunk
    chunk_args = [(i, chunk, api_key) for i, chunk in enumerate(audio_chunks)]

    # Process chunks in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_transcribe_single_chunk, args): args[0]
                   for args in chunk_args}

        for future in as_completed(futures):
            try:
                chunk_index, transcript = future.result()
                transcriptions[chunk_index] = transcript
                completed += 1
                if progress_callback:
                    progress_callback(completed, len(audio_chunks))
            except Exception as e:
                # Log error but continue with other chunks
                print(f"Chunk transcription error: {e}")
                completed += 1
                continue

    # Combine transcriptions in order, handling overlaps
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
    # Filter out empty transcriptions
    transcriptions = [t for t in transcriptions if t and t.strip()]

    if not transcriptions:
        return ""

    if len(transcriptions) == 1:
        return transcriptions[0]

    result = transcriptions[0]

    for i in range(1, len(transcriptions)):
        current = transcriptions[i]

        if not current:
            continue

        result_words = result.split()
        current_words = current.split()

        if not result_words or not current_words:
            result += " " + current
            continue

        # Check for overlap in last 5 words of result vs first 5 words of current
        overlap_found = False
        for overlap_len in range(min(5, len(result_words), len(current_words)), 0, -1):
            result_end = " ".join(result_words[-overlap_len:]).lower()
            current_start = " ".join(current_words[:overlap_len]).lower()

            if result_end == current_start:
                # Found overlap, merge without duplication
                result = " ".join(result_words) + " " + " ".join(current_words[overlap_len:])
                overlap_found = True
                break

        if not overlap_found:
            # No overlap found, just concatenate
            result = result + " " + current

    return result.strip()


def get_audio_duration_seconds(audio: AudioSegment) -> float:
    """Get audio duration in seconds."""
    return len(audio) / 1000.0


def get_chunk_info(audio: AudioSegment) -> Tuple[int, float]:
    """
    Get information about how audio will be chunked.
    Uses same adaptive logic as process_audio_for_transcription.

    Args:
        audio: AudioSegment to analyze

    Returns:
        Tuple of (num_chunks, total_duration_seconds)
    """
    # For short audio, return 1 chunk
    if len(audio) < 25000:
        return 1, get_audio_duration_seconds(audio)

    # First remove silence to get accurate estimate
    cleaned = remove_silence(audio)
    cleaned_len = len(cleaned)

    # Use same adaptive chunk sizing
    if cleaned_len > 300000:  # > 5 minutes
        chunk_duration = 60000
        overlap = 2000
    elif cleaned_len > 120000:  # > 2 minutes
        chunk_duration = 45000
        overlap = 1500
    else:
        chunk_duration = 30000
        overlap = 1000

    chunks = chunk_audio(cleaned, chunk_duration, overlap)
    return len(chunks), get_audio_duration_seconds(cleaned)


def audio_to_bytes(audio: AudioSegment, format: str = "mp3") -> bytes:
    """Convert AudioSegment to bytes. Default to MP3 for smaller size."""
    buffer = io.BytesIO()
    audio.export(buffer, format=format)
    buffer.seek(0)
    return buffer.read()
