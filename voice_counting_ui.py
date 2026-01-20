"""
Voice Counting UI - Streamlit interface for voice-based inventory counting.

This module provides the complete voice counting user interface including:
- Voice input (browser speech + audio file upload)
- Session management
- Text log editing
- Excel export
"""

import streamlit as st
import pandas as pd
import uuid
from datetime import datetime
from io import BytesIO
import json

# Audio recording component
try:
    from audiorecorder import audiorecorder
    AUDIO_RECORDER_AVAILABLE = True
except ImportError:
    AUDIO_RECORDER_AVAILABLE = False

# Speech recognition - using OpenAI Whisper for better accuracy
try:
    import whisper
    import torch
    WHISPER_AVAILABLE = True
    # Load Whisper model once (base model is fast and accurate enough)
    # Model sizes: tiny, base, small, medium, large (larger = more accurate but slower)
    WHISPER_MODEL = None  # Lazy load on first use
except ImportError:
    WHISPER_AVAILABLE = False

# Fallback to Google Speech Recognition if Whisper not available
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False

from models import VoiceCountSession, VoiceCountRecord
from voice_matcher import VoiceItemMatcher
from voice_export import export_voice_count_to_excel, get_inventory_order_from_template, get_default_inventory_order
from audio_processing import (
    process_audio_for_transcription,
    transcribe_with_openai_api,
    get_chunk_info,
    get_audio_duration_seconds,
    remove_silence
)
import storage


def render_voice_counting_tab(dataset, inventory_layout=None):
    """
    Render the Voice Counting tab in the Streamlit app.

    Args:
        dataset: InventoryDataset object
        inventory_layout: Optional dict from inventory_layout.json
    """
    st.header("🎙️ Voice Counting")

    # Initialize session state
    if 'voice_session' not in st.session_state:
        st.session_state.voice_session = None
    if 'voice_matcher' not in st.session_state:
        st.session_state.voice_matcher = VoiceItemMatcher(dataset)
    if 'pending_match' not in st.session_state:
        st.session_state.pending_match = None
    if 'inventory_order' not in st.session_state:
        st.session_state.inventory_order = None
    if 'pending_transcript' not in st.session_state:
        st.session_state.pending_transcript = None
    if 'transcript_ready_to_map' not in st.session_state:
        st.session_state.transcript_ready_to_map = False

    # Top section: Session management
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        if st.button("📝 New Session", use_container_width=True):
            session_name = f"Count {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            st.session_state.voice_session = VoiceCountSession(
                session_id=str(uuid.uuid4()),
                created_at=datetime.now(),
                updated_at=datetime.now(),
                session_name=session_name,
                status="in_progress"
            )
            st.session_state.pending_match = None
            st.rerun()

    with col2:
        # Load existing session
        sessions = storage.list_voice_count_sessions(limit=50)
        if sessions:
            session_options = {
                f"{s['session_name']} ({s['total_items_counted']} items)": s['session_id']
                for s in sessions
            }
            selected_session_name = st.selectbox(
                "Load Session",
                options=["-- Select --"] + list(session_options.keys()),
                key="session_selector"
            )

            if selected_session_name != "-- Select --":
                session_id = session_options[selected_session_name]
                if st.session_state.voice_session is None or st.session_state.voice_session.session_id != session_id:
                    loaded_session = storage.load_voice_count_session(session_id)
                    if loaded_session:
                        st.session_state.voice_session = loaded_session
                        st.rerun()

    with col3:
        if st.session_state.voice_session:
            if st.button("💾 Save", use_container_width=True):
                storage.save_voice_count_session(st.session_state.voice_session)
                st.success("Saved!")

    # If no session, show instructions
    if not st.session_state.voice_session:
        st.info("👆 Create a new session or load an existing one to get started")
        st.markdown("""
        ### How Voice Counting Works:

        1. **Start a Session** - Create a new counting session
        2. **Upload Template** (optional) - Upload your Excel inventory sheet to set the export order
        3. **Count Items** - Use voice input or type manually
        4. **Review & Edit** - Check the transcript log and verify matches
        5. **Export to Excel** - Download results in your inventory sheet order
        """)
        return

    # Active session UI
    session = st.session_state.voice_session

    st.markdown(f"### Session: {session.session_name}")

    # Session info metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Items Counted", session.total_items_counted)
    with col2:
        verified_count = len(session.get_verified_records())
        st.metric("Verified", f"{verified_count} ({verified_count/max(session.total_items_counted, 1)*100:.0f}%)")
    with col3:
        high_conf = len([r for r in session.records if r.confidence_score >= 0.85])
        st.metric("High Confidence", f"{high_conf} ({high_conf/max(session.total_items_counted, 1)*100:.0f}%)")
    with col4:
        unmatched = len(session.get_unmatched_records())
        st.metric("Unmatched", unmatched, delta_color="inverse")

    st.markdown("---")

    # Excel template upload for custom ordering
    with st.expander("📊 Upload Excel Template for Custom Export Order"):
        st.markdown("Upload your inventory Excel sheet to match the export order to your physical counting sheet.")
        template_file = st.file_uploader(
            "Upload Excel Template",
            type=['xlsx', 'xls'],
            key="template_uploader"
        )

        if template_file:
            order = get_inventory_order_from_template(template_file)
            if order:
                st.session_state.inventory_order = order
                st.session_state.voice_session.inventory_order = order
                st.session_state.voice_session.template_file_name = template_file.name
                st.success(f"✓ Template loaded: {len(order)} items in order")
            else:
                st.error("Could not read item order from template")

    st.markdown("---")

    # Voice/Text Input Section
    st.markdown("### 🎤 Count Items")

    # AI Assistant toggle (premium feature)
    col1, col2 = st.columns([3, 1])
    with col1:
        st.info("💡 **Tip**: You can also input weights! Say \"Buffalo Trace 850 grams\" or \"Keg 65 pounds\"")
    with col2:
        use_ai_assistant = st.checkbox(
            "🤖 AI Assistant",
            value=False,
            help="Premium: AI helps parse speech, handles corrections and duplicates (~$0.001/session)"
        )
        if 'use_ai_assistant' not in st.session_state:
            st.session_state.use_ai_assistant = False
        st.session_state.use_ai_assistant = use_ai_assistant

    input_method = st.radio(
        "Input Method",
        ["💬 Manual Entry", "🎤 Voice Recording (Browser)", "📁 Upload Audio File"],
        horizontal=True
    )

    if input_method == "💬 Manual Entry":
        render_manual_input(session, dataset)
    elif input_method == "🎤 Voice Recording (Browser)":
        render_browser_voice_input(session, dataset)
    elif input_method == "📁 Upload Audio File":
        render_audio_file_input(session, dataset)

    st.markdown("---")

    # Transcript Log Editor
    render_transcript_log(session, dataset)

    st.markdown("---")

    # Export Section
    render_export_section(session, dataset, inventory_layout)


def render_manual_input(session, dataset):
    """Render manual text entry interface."""
    st.markdown("Type item name and quantity (e.g., 'Buffalo Trace 3' or 'Titos 5')")

    col1, col2 = st.columns([4, 1])

    with col1:
        transcript = st.text_input(
            "Item & Count",
            key="manual_transcript",
            placeholder="e.g., 'Buffalo Trace 3' or 'Titos 5'"
        )

    with col2:
        submit_btn = st.button("Add", key="manual_submit", use_container_width=True)

    if submit_btn and transcript:
        process_transcript(session, transcript, dataset)
        st.rerun()


def render_browser_voice_input(session, dataset):
    """Render browser-based voice recording interface with two-step transcription flow."""
    if not AUDIO_RECORDER_AVAILABLE:
        st.warning("⚠️ Audio recorder not available. Install with: `pip install streamlit-audiorecorder`")
        st.info("💡 Use Manual Entry or Upload Audio File instead")
        return

    st.markdown("**🎤 Continuous Recording Mode**")
    st.info("💡 Click Start to record. Say multiple items: 'Buffalo Trace 3, Titos 5, Makers 850 grams...'. Click Stop when done.")

    # Check if we have a pending transcript to display
    if st.session_state.pending_transcript:
        render_transcript_editor(session, dataset)
        return

    # Record audio with better UI and visualizer
    audio = audiorecorder(
        start_prompt="🎤 Start Recording",
        stop_prompt="⏹️ Stop Recording",
        pause_prompt="",  # Hide pause button
        show_visualizer=True,
        key="voice_recorder"
    )

    # Check if audio was recorded (AudioSegment has length > 0)
    if len(audio) > 0:
        # Show original audio duration
        original_duration = get_audio_duration_seconds(audio)
        st.caption(f"Recorded: {original_duration:.1f} seconds")

        # Play back the recorded audio
        st.audio(audio.export().read(), format="audio/wav")

        # Show processing info
        num_chunks, cleaned_duration = get_chunk_info(audio)
        if cleaned_duration < original_duration:
            st.caption(f"After silence removal: {cleaned_duration:.1f}s ({num_chunks} chunk{'s' if num_chunks > 1 else ''})")

        if st.button("🔄 Transcribe Audio", key="transcribe_btn", type="primary"):
            # Check for OpenAI API key
            api_key = None
            if "openai" in st.secrets and "api_key" in st.secrets["openai"]:
                api_key = st.secrets["openai"]["api_key"]

            if not api_key:
                st.error("⚠️ OpenAI API key required. Add it to your Streamlit secrets.")
                return

            with st.spinner("Processing audio (removing silences, chunking)..."):
                # Process audio: remove silence and chunk
                chunks = process_audio_for_transcription(audio)

            try:
                if len(chunks) > 3:
                    # Long recording - show progress bar
                    progress_bar = st.progress(0, text=f"Transcribing 0/{len(chunks)} chunks...")
                    def update_progress(completed, total):
                        progress_bar.progress(completed / total, text=f"Transcribing {completed}/{total} chunks...")
                    transcript = transcribe_with_openai_api(chunks, api_key, progress_callback=update_progress)
                    progress_bar.empty()
                else:
                    # Short recording - just spinner
                    with st.spinner(f"Transcribing {len(chunks)} audio chunk{'s' if len(chunks) > 1 else ''}..."):
                        transcript = transcribe_with_openai_api(chunks, api_key)

                if transcript:
                    # Store transcript for editing
                    st.session_state.pending_transcript = transcript
                    st.session_state.transcript_ready_to_map = False
                    st.rerun()
                else:
                    st.error("Could not transcribe audio. Please try again.")
            except Exception as e:
                st.error(f"Transcription error: {str(e)}")


def format_transcript_with_newlines(transcript: str) -> str:
    """Format transcript with newlines after each number for easier reading/editing."""
    import re
    # Insert newline after numbers (but not before weight units)
    # Pattern: number followed by space and a letter (start of next item)
    formatted = re.sub(
        r'(\d+\.?\d*)\s*,?\s*(?!(?:grams?|g|pounds?|lbs?|lb|oz|ounces?)\b)([A-Za-z])',
        r'\1\n\2',
        transcript,
        flags=re.IGNORECASE
    )
    # Also handle period followed by space and capital letter (sentence boundary)
    formatted = re.sub(r'\.\s+([A-Z])', r'.\n\1', formatted)
    return formatted.strip()


def render_transcript_editor(session, dataset):
    """Render the editable transcript text box and mapping controls."""
    st.markdown("### 📝 Review & Edit Transcript")
    st.info("💡 Edit the transcript below if needed (one item per line), then click 'Map Items' to match to your inventory.")

    # Format transcript with newlines for easier editing
    display_transcript = format_transcript_with_newlines(st.session_state.pending_transcript)

    # Editable text area for transcript - larger size
    edited_transcript = st.text_area(
        "Transcription",
        value=display_transcript,
        height=600,
        key="transcript_editor",
        help="Edit the transcript to fix any transcription errors before mapping to items. One item per line."
    )

    # Action buttons
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        if st.button("✅ Map Items", key="map_items_btn", type="primary", use_container_width=True):
            if edited_transcript.strip():
                use_ai = st.session_state.get('use_ai_assistant', False)
                result = process_multi_item_transcript(session, edited_transcript, dataset, use_ai=use_ai)

                # Handle AI vs regular response
                if use_ai and isinstance(result, tuple):
                    items_processed, ai_feedback = result
                    if items_processed > 0:
                        st.success(f"✅ {ai_feedback}")
                        # Clear pending transcript
                        st.session_state.pending_transcript = None
                        st.session_state.transcript_ready_to_map = False
                        st.rerun()
                    else:
                        st.warning(ai_feedback)
                else:
                    items_processed = result
                    if items_processed > 0:
                        st.success(f"✅ Added {items_processed} items to session!")
                        # Clear pending transcript
                        st.session_state.pending_transcript = None
                        st.session_state.transcript_ready_to_map = False
                        st.rerun()
                    else:
                        st.warning("⚠️ No items could be matched. Try editing the transcript.")
            else:
                st.warning("Please enter some text to map.")

    with col2:
        if st.button("🔄 Record New", key="record_new_btn", use_container_width=True):
            st.session_state.pending_transcript = None
            st.session_state.transcript_ready_to_map = False
            st.rerun()

    with col3:
        if st.button("❌ Cancel", key="cancel_transcript_btn", use_container_width=True):
            st.session_state.pending_transcript = None
            st.session_state.transcript_ready_to_map = False
            st.rerun()


def render_audio_file_input(session, dataset):
    """Render audio file upload interface with two-step transcription flow."""
    st.markdown("**📁 Upload Audio File**")
    st.info("💡 Upload a recording with multiple items: 'Buffalo Trace 3, Titos 5, Makers 850 grams...'")

    # Check if we have a pending transcript to display
    if st.session_state.pending_transcript:
        render_transcript_editor(session, dataset)
        return

    audio_file = st.file_uploader(
        "Upload Audio",
        type=['wav', 'mp3', 'flac', 'm4a'],
        key="audio_file_uploader"
    )

    if audio_file:
        st.audio(audio_file)

        if st.button("🔄 Transcribe Audio", key="file_transcribe_btn", type="primary"):
            # Check for OpenAI API key
            api_key = None
            if "openai" in st.secrets and "api_key" in st.secrets["openai"]:
                api_key = st.secrets["openai"]["api_key"]

            if not api_key:
                st.error("⚠️ OpenAI API key required. Add it to your Streamlit secrets.")
                return

            with st.spinner("Loading and processing audio..."):
                try:
                    # Load audio file with pydub
                    from pydub import AudioSegment
                    audio_file.seek(0)

                    # Determine format from file extension
                    file_ext = audio_file.name.split('.')[-1].lower()
                    if file_ext == 'm4a':
                        file_ext = 'mp4'  # pydub uses mp4 for m4a

                    audio = AudioSegment.from_file(audio_file, format=file_ext)

                    # Show original duration
                    original_duration = get_audio_duration_seconds(audio)
                    st.caption(f"Audio length: {original_duration:.1f} seconds")

                    # Process audio: remove silence and chunk
                    chunks = process_audio_for_transcription(audio)

                    # Show processing info
                    cleaned_duration = sum(len(c) for c in chunks) / 1000.0
                    if cleaned_duration < original_duration:
                        st.caption(f"After silence removal: {cleaned_duration:.1f}s ({len(chunks)} chunk{'s' if len(chunks) > 1 else ''})")

                except Exception as e:
                    st.error(f"Could not load audio file: {str(e)}")
                    return

            try:
                if len(chunks) > 3:
                    # Long recording - show progress bar
                    progress_bar = st.progress(0, text=f"Transcribing 0/{len(chunks)} chunks...")
                    def update_progress(completed, total):
                        progress_bar.progress(completed / total, text=f"Transcribing {completed}/{total} chunks...")
                    transcript = transcribe_with_openai_api(chunks, api_key, progress_callback=update_progress)
                    progress_bar.empty()
                else:
                    # Short recording - just spinner
                    with st.spinner(f"Transcribing {len(chunks)} audio chunk{'s' if len(chunks) > 1 else ''}..."):
                        transcript = transcribe_with_openai_api(chunks, api_key)

                if transcript:
                    # Store transcript for editing
                    st.session_state.pending_transcript = transcript
                    st.session_state.transcript_ready_to_map = False
                    st.rerun()
                else:
                    st.error("Could not transcribe audio. Please try again.")
            except Exception as e:
                st.error(f"Transcription error: {str(e)}")


def process_transcript(session, transcript, dataset):
    """Process a transcript and add to session."""
    matcher = st.session_state.voice_matcher

    # Parse item name, count, and optional weight unit
    matches, count_value, weight_unit = matcher.match_with_count(transcript)

    # If weight was detected, we need to calculate fill percentage
    is_weight_input = weight_unit is not None
    actual_count = count_value
    notes = None

    if not matches:
        # No match found
        record = VoiceCountRecord(
            record_id=str(uuid.uuid4()),
            session_id=session.session_id,
            timestamp=datetime.now(),
            raw_transcript=transcript,
            cleaned_transcript=transcript,
            matched_item_id=None,
            count_value=count_value,
            confidence_score=0.0,
            match_method="manual",
            is_verified=False,
            notes=f"Weight: {count_value} {weight_unit}" if is_weight_input else None
        )
        session.add_record(record)
        st.warning(f"⚠️ No match found for: '{transcript}'. Added to log for manual review.")
    else:
        # Show top match for confirmation
        top_match = matches[0]
        item = dataset.items[top_match.item_id]

        # If weight input, calculate fill percentage
        if is_weight_input:
            fill_pct = item.calculate_fill_from_weight(count_value, input_unit=weight_unit)
            actual_count = fill_pct
            notes = f"{count_value} {weight_unit} = {fill_pct:.0%} full"

        # Auto-verify high confidence matches
        if top_match.confidence >= 0.85:
            record = VoiceCountRecord(
                record_id=str(uuid.uuid4()),
                session_id=session.session_id,
                timestamp=datetime.now(),
                raw_transcript=transcript,
                cleaned_transcript=transcript,
                matched_item_id=top_match.item_id,
                count_value=actual_count,
                confidence_score=1.0 if is_weight_input else top_match.confidence,  # Weight is precise
                match_method="weight" if is_weight_input else top_match.method,
                is_verified=True,
                notes=notes
            )
            session.add_record(record)

            if is_weight_input:
                st.success(f"⚖️ Weighed: {item.display_name} = {actual_count:.2f} bottles ({count_value} {weight_unit})")
            else:
                st.success(f"✓ Matched: {item.display_name} - Count: {count_value} (Confidence: {top_match.confidence:.0%})")
        else:
            # Show confirmation dialog for lower confidence
            st.session_state.pending_match = {
                'transcript': transcript,
                'matches': matches,
                'count_value': actual_count,
                'weight_unit': weight_unit,
                'notes': notes
            }


def render_transcript_log(session, dataset):
    """Render the transcript log editor."""
    st.markdown("### 📋 Transcript Log")

    if not session.records:
        st.info("No records yet. Start counting above!")
        return

    # Group counts by item
    item_groups = {}
    for record in session.records:
        if record.matched_item_id:
            if record.matched_item_id not in item_groups:
                item_groups[record.matched_item_id] = []
            item_groups[record.matched_item_id].append(record)

    # Display grouped summary
    if item_groups:
        st.markdown("#### 📊 Summary by Item")

        for item_id, records in sorted(item_groups.items()):
            item = dataset.items.get(item_id)
            if not item:
                continue

            # Calculate total and breakdown
            counts = [r.count_value for r in records if r.count_value is not None]
            total = sum(counts)
            breakdown = " + ".join([f"{c:.2f}" if c < 1 else f"{c:.0f}" for c in counts])

            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{item.display_name}**: `{total:.2f}` = {breakdown}")
            with col2:
                st.caption(f"{len(records)} count{'s' if len(records) > 1 else ''}")

        st.markdown("---")

    # Display individual records with edit/delete
    st.markdown("#### 📝 Individual Records")

    for i, record in enumerate(session.records):
        item_name = ""
        if record.matched_item_id and record.matched_item_id in dataset.items:
            item_name = dataset.items[record.matched_item_id].display_name

        with st.expander(
            f"{record.timestamp.strftime('%H:%M:%S')} - {item_name or record.raw_transcript} - {record.count_value or 'No count'}",
            expanded=False
        ):
            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                # Edit count
                new_count = st.number_input(
                    "Count",
                    value=float(record.count_value) if record.count_value else 0.0,
                    step=0.1,
                    format="%.2f",
                    key=f"edit_count_{i}"
                )

                if new_count != record.count_value:
                    if st.button("💾 Save Count", key=f"save_count_{i}"):
                        record.count_value = new_count
                        session.updated_at = datetime.now()
                        storage.save_voice_count_session(session)
                        st.success("Updated!")
                        st.rerun()

            with col2:
                # Verify toggle
                if st.button(
                    "✓ Verified" if record.is_verified else "⚠ Verify",
                    key=f"verify_{i}",
                    type="primary" if not record.is_verified else "secondary"
                ):
                    record.is_verified = not record.is_verified
                    session.updated_at = datetime.now()
                    storage.save_voice_count_session(session)
                    st.rerun()

            with col3:
                # Delete button
                if st.button("🗑️ Delete", key=f"delete_{i}"):
                    session.records.pop(i)
                    session.total_items_counted = len(session.records)
                    session.updated_at = datetime.now()
                    storage.save_voice_count_session(session)
                    st.success("Deleted!")
                    st.rerun()

            # Show details
            st.caption(f"**Transcript:** {record.raw_transcript}")
            st.caption(f"**Method:** {record.match_method} | **Confidence:** {record.confidence_score:.0%}")
            if record.notes:
                st.caption(f"**Notes:** {record.notes}")

    # Action buttons
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("✓ Verify All", use_container_width=True):
            for record in session.records:
                if record.matched_item_id:
                    record.is_verified = True
            session.updated_at = datetime.now()
            storage.save_voice_count_session(session)
            st.success("All matched records verified!")
            st.rerun()

    with col2:
        if st.button("🔄 Re-match All", use_container_width=True):
            rematch_all_records(session, dataset)
            storage.save_voice_count_session(session)
            st.success("Re-matched all records!")
            st.rerun()

    with col3:
        if st.button("🗑️ Clear All", use_container_width=True):
            if st.session_state.get('confirm_clear', False):
                session.records = []
                session.total_items_counted = 0
                session.updated_at = datetime.now()
                storage.save_voice_count_session(session)
                st.session_state.confirm_clear = False
                st.success("All records cleared!")
                st.rerun()
            else:
                st.session_state.confirm_clear = True
                st.warning("Click again to confirm deletion")

    with col4:
        # Download transcript as CSV with grouped format
        csv_data = []
        for item_id, records in sorted(item_groups.items()):
            item = dataset.items.get(item_id)
            if not item:
                continue
            counts = [r.count_value for r in records if r.count_value is not None]
            total = sum(counts)
            csv_data.append({
                'Item': item.display_name,
                'Total': total,
                'Counts': ', '.join([f"{c:.2f}" for c in counts])
            })

        if csv_data:
            csv_df = pd.DataFrame(csv_data)
            csv_string = csv_df.to_csv(index=False)
            st.download_button(
                "📄 Download CSV",
                data=csv_string,
                file_name=f"counts_{session.session_name}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.button("📄 Download CSV", disabled=True, use_container_width=True)


def render_export_section(session, dataset, inventory_layout):
    """Render the export section."""
    st.markdown("### 📥 Export")

    # Get inventory order
    if session.inventory_order:
        order = session.inventory_order
        order_source = f"Custom template: {session.template_file_name}"
    elif st.session_state.inventory_order:
        order = st.session_state.inventory_order
        order_source = "Custom template (uploaded this session)"
    else:
        order = get_default_inventory_order(dataset, inventory_layout)
        order_source = "Default order (by location/category)"

    st.info(f"📊 Export order: {order_source}")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("📥 Export to Excel", use_container_width=True, type="primary"):
            with st.spinner("Generating Excel file..."):
                # Get latest inventory for variance analysis
                system_inventory = None
                if not dataset.records.empty:
                    # Get most recent inventory
                    latest_date = dataset.records['week_date'].max()
                    system_inventory = dataset.records[dataset.records['week_date'] == latest_date]

                excel_buffer = export_voice_count_to_excel(
                    session,
                    dataset,
                    inventory_order=order,
                    system_inventory=system_inventory
                )

                filename = f"voice_count_{session.session_name.replace(' ', '_')}.xlsx"

                st.download_button(
                    label="💾 Download Excel File",
                    data=excel_buffer.getvalue(),
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

                # Mark session as exported
                session.status = "exported"
                session.updated_at = datetime.now()
                storage.save_voice_count_session(session)

    with col2:
        if st.button("🗑️ Delete Session", use_container_width=True):
            if st.session_state.get('confirm_delete_session', False):
                storage.delete_voice_count_session(session.session_id)
                st.session_state.voice_session = None
                st.session_state.confirm_delete_session = False
                st.success("Session deleted!")
                st.rerun()
            else:
                st.session_state.confirm_delete_session = True
                st.warning("Click again to confirm deletion")


def rematch_all_records(session, dataset):
    """Re-match all records with current matcher."""
    matcher = st.session_state.voice_matcher

    for record in session.records:
        if not record.matched_item_id:  # Only re-match unmatched records
            matches, count_value, weight_unit = matcher.match_with_count(record.raw_transcript)
            if matches:
                top_match = matches[0]
                item = dataset.items[top_match.item_id]

                # Check if this is a weight input
                if weight_unit and count_value is not None:
                    fill_pct = item.calculate_fill_from_weight(count_value, input_unit=weight_unit)
                    record.count_value = fill_pct
                    record.match_method = "weight"
                    record.confidence_score = 1.0
                    record.notes = f"{count_value} {weight_unit} = {fill_pct:.0%} full"
                else:
                    record.match_method = top_match.method
                    record.confidence_score = top_match.confidence
                    if count_value is not None:
                        record.count_value = count_value

                record.matched_item_id = top_match.item_id

                # Auto-verify high confidence
                if record.confidence_score >= 0.85:
                    record.is_verified = True

    session.updated_at = datetime.now()


def process_with_ai_assistant(session, transcript, dataset):
    """
    Process transcript using AI assistant (premium feature).

    The AI helps parse complex speech patterns, provides confirmation,
    and guides the user through the counting process.

    Args:
        session: Current VoiceCountSession
        transcript: Voice transcript
        dataset: InventoryDataset

    Returns:
        Tuple of (items_processed, ai_feedback_message) or None if AI fails (to trigger fallback)
    """
    # Check if OpenAI is available
    try:
        from openai import OpenAI
        import json
    except ImportError:
        return None  # Signal to use fallback

    # Check for API key
    if "openai" not in st.secrets or "api_key" not in st.secrets["openai"]:
        return None  # Signal to use fallback

    try:
        client = OpenAI(api_key=st.secrets["openai"]["api_key"])

        # Create prompt for AI
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Cheap and fast
            messages=[
                {
                    "role": "system",
                    "content": """You are an inventory counting assistant. Extract items and counts from user speech.

Handle various formats and edge cases:
- Continuous speech without commas: "Tito's 7.0 Buffalo Trace 3.0 Maker's Mark 5.0" → extract all 3 items
- Decimal numbers: "7.0" or "3.0" should be parsed as 7 and 3 (integers)
- Duplicates: "Ketel One Ketel One three" → 3 Ketel One (person repeated themselves)
- Corrections: "Tito's... no wait Buffalo Trace two" → 2 Buffalo Trace (correction)
- Hesitations: "Jim Beam um... three" → 3 Jim Beam (hesitation)
- Multiple same items: "Tito's 7 ... Tito's 5" → Two separate entries: 7 Tito's and 5 Tito's

IMPORTANT: When items are spoken continuously without clear separators (e.g., "Tito's 7.0 Buffalo Trace 3.0"),
use the pattern where a NUMBER followed by a PRODUCT NAME indicates the end of the previous item.

Return JSON format:
{
  "items": [
    {"name": "Buffalo Trace", "count": 3, "unit": null},
    {"name": "Tito's Vodka", "count": 7, "unit": null},
    {"name": "Tito's Vodka", "count": 5, "unit": null}
  ],
  "confirmation": "Got it - 3 Buffalo Trace, 7 Tito's, and 5 Tito's. What else?"
}

If you can't extract any items, return empty items array with helpful message."""
                },
                {
                    "role": "user",
                    "content": transcript
                }
            ],
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"}  # Force JSON output
        )

        # Parse AI response
        ai_content = response.choices[0].message.content

        if not ai_content or not ai_content.strip():
            return None  # Signal to use fallback

        result = json.loads(ai_content)

        # Process each item
        items_processed = 0
        matcher = st.session_state.voice_matcher

        for item in result.get("items", []):
            item_name = item.get("name")
            if not item_name:
                continue

            count_value = item.get("count")
            unit = item.get("unit")

            # Match to inventory
            matches = matcher.match(item_name, top_n=3)

            if matches and matches[0].confidence >= 0.65:
                top_match = matches[0]
                inventory_item = dataset.items[top_match.item_id]

                # Handle weight conversion if needed
                is_weight_input = unit in ["grams", "pounds"]
                actual_count = count_value
                notes = None

                if is_weight_input and count_value is not None:
                    fill_pct = inventory_item.calculate_fill_from_weight(count_value, input_unit=unit)
                    actual_count = fill_pct
                    notes = f"{count_value} {unit} = {fill_pct:.0%} full"

                # Create record
                record = VoiceCountRecord(
                    record_id=str(uuid.uuid4()),
                    session_id=session.session_id,
                    timestamp=datetime.now(),
                    raw_transcript=transcript,
                    cleaned_transcript=item_name,
                    matched_item_id=top_match.item_id,
                    count_value=actual_count,
                    confidence_score=top_match.confidence,
                    match_method="ai_assistant",
                    is_verified=top_match.confidence >= 0.85,
                    notes=notes
                )
                session.add_record(record)
                items_processed += 1

        # Update session
        session.updated_at = datetime.now()
        storage.save_voice_count_session(session)

        # Return with AI feedback
        return items_processed, result.get("confirmation", "Items processed!")

    except json.JSONDecodeError as e:
        st.warning(f"⚠️ AI response parsing failed, using standard matching...")
        return None  # Signal to use fallback
    except Exception as e:
        st.warning(f"⚠️ AI Assistant unavailable ({str(e)[:50]}...), using standard matching...")
        return None  # Signal to use fallback


def clean_transcript_smart(transcript: str) -> str:
    """
    Clean transcript by handling common speech patterns.

    Handles:
    - Duplicates: "Ketel One Ketel One three" → "Ketel One three"
    - Corrections: "Tito's... no wait Buffalo Trace three" → "Buffalo Trace three"
    - Hesitations: "Jim Beam... two" → "Jim Beam two"
    - Filler words: "um", "uh", "like"

    Args:
        transcript: Raw voice transcript

    Returns:
        Cleaned transcript
    """
    import re

    # Remove filler words
    filler_words = ['um', 'uh', 'like', 'you know', 'so', 'actually', 'basically']
    cleaned = transcript.lower()
    for filler in filler_words:
        cleaned = re.sub(r'\b' + filler + r'\b', '', cleaned, flags=re.IGNORECASE)

    # Handle corrections: "X... no wait Y" → keep only Y
    cleaned = re.sub(r'.+?(no wait|wait|actually)\s+(.+)', r'\2', cleaned, flags=re.IGNORECASE)

    # Remove excessive ellipses/pauses
    cleaned = re.sub(r'\.{2,}', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # Handle duplicates: if same item appears twice in a row, keep only the one with a number
    # "ketel one ketel one three" → "ketel one three"
    words = cleaned.split()
    result = []
    i = 0
    while i < len(words):
        # Look ahead to see if next few words are a duplicate
        if i < len(words) - 2:
            # Check if we have "word word number" pattern
            potential_dup = ' '.join(words[i:i+2])
            potential_with_count = ' '.join(words[i+2:i+4]) if i+3 < len(words) else words[i+2] if i+2 < len(words) else ''

            # If the first two words appear again, and the second mention has a number, skip first mention
            if i+4 < len(words) and ' '.join(words[i+2:i+4]) == potential_dup:
                # Skip the first mention
                i += 2
                continue

        result.append(words[i])
        i += 1

    cleaned = ' '.join(result)

    # Restore original casing for better matching
    return cleaned.title() if cleaned else transcript


def process_multi_item_transcript(session, transcript, dataset, use_ai=False):
    """
    Process multiple items from a continuous recording transcript.

    Example input: "Buffalo Trace 3, Titos 5, Makers Mark 850 grams, Jim Beam 2"

    Args:
        session: Current VoiceCountSession
        transcript: Full transcript containing multiple items
        dataset: InventoryDataset
        use_ai: If True, use AI assistant for parsing (premium feature)

    Returns:
        Number of items successfully processed (or tuple with AI feedback if use_ai=True)
    """
    # Check if AI mode is enabled and available
    if use_ai:
        ai_result = process_with_ai_assistant(session, transcript, dataset)
        # If AI succeeded (returned tuple), return the result
        if ai_result is not None:
            return ai_result
        # If AI failed (returned None), fall through to standard parsing
        st.info("Using standard matching...")

    # Standard parsing: Smart cleaning + regular parsing
    transcript = clean_transcript_smart(transcript)
    matcher = st.session_state.voice_matcher

    # Normalize decimal numbers (7.0 → 7, 3.0 → 3) to prevent bad splits
    import re
    transcript = re.sub(r'(\d+)\.0+\b', r'\1', transcript)  # Remove .0 from numbers

    # Detect continuous speech pattern: "Item1 Number1 Item2 Number2"
    # Insert delimiter after each number-word pair, but NOT if followed by weight units
    # Example: "Chambord 7 Buffalo Trace 6" → "Chambord 7|Buffalo Trace 6"
    # But keep: "Makers 850 grams" → "Makers 850 grams" (no split)
    transcript = re.sub(
        r'(\d+)\s+(?!(?:grams?|g|pounds?|lbs?|lb)\b)([a-zA-Z])',  # Negative lookahead for weight units
        r'\1|\2',  # Insert delimiter between number and word (if not a weight unit)
        transcript,
        flags=re.IGNORECASE
    )

    # Split transcript by common separators (comma, "and", semicolon, newline, now includes |)
    separators = ['\n', ',', ' and ', ';', '|']

    # Replace all separators with a common delimiter
    normalized = transcript
    for sep in separators:
        normalized = normalized.replace(sep, '|')

    # Split into individual item segments
    segments = [s.strip() for s in normalized.split('|') if s.strip()]

    items_processed = 0

    for segment in segments:
        # Skip very short segments (likely transcription noise)
        if len(segment) < 3:
            continue

        # Process each segment through the existing transcript processor
        matches, count_value, weight_unit = matcher.match_with_count(segment)

        if not matches:
            # No match found - add to log for manual review
            record = VoiceCountRecord(
                record_id=str(uuid.uuid4()),
                session_id=session.session_id,
                timestamp=datetime.now(),
                raw_transcript=segment,
                cleaned_transcript=segment,
                matched_item_id=None,
                count_value=count_value,
                confidence_score=0.0,
                match_method="voice",
                is_verified=False,
                notes=f"Weight: {count_value} {weight_unit}" if weight_unit else "Unmatched from continuous recording"
            )
            session.add_record(record)
            items_processed += 1
        else:
            # Process the match
            top_match = matches[0]
            item = dataset.items[top_match.item_id]

            # Calculate actual count (handle weight inputs)
            is_weight_input = weight_unit is not None
            actual_count = count_value
            notes = None

            if is_weight_input and count_value is not None:
                fill_pct = item.calculate_fill_from_weight(count_value, input_unit=weight_unit)
                actual_count = fill_pct
                notes = f"{count_value} {weight_unit} = {fill_pct:.0%} full"

            # Create record
            record = VoiceCountRecord(
                record_id=str(uuid.uuid4()),
                session_id=session.session_id,
                timestamp=datetime.now(),
                raw_transcript=segment,
                cleaned_transcript=segment,
                matched_item_id=top_match.item_id,
                count_value=actual_count,
                confidence_score=1.0 if is_weight_input else top_match.confidence,
                match_method="weight" if is_weight_input else top_match.method,
                is_verified=top_match.confidence >= 0.85,  # Auto-verify high confidence
                notes=notes
            )
            session.add_record(record)
            items_processed += 1

    # Update session
    session.updated_at = datetime.now()
    storage.save_voice_count_session(session)

    return items_processed


def _load_whisper_model():
    """Lazy load Whisper model on first use."""
    global WHISPER_MODEL
    if WHISPER_MODEL is None:
        # Use 'base' model - good balance of speed and accuracy
        # Options: tiny, base, small, medium, large
        WHISPER_MODEL = whisper.load_model("base")
    return WHISPER_MODEL


def transcribe_audio_bytes(audio_bytes):
    """
    Transcribe audio from bytes using OpenAI Whisper (preferred) or Google Speech as fallback.

    Whisper provides ~7.4% WER (Word Error Rate) vs Google's higher error rate.
    """
    import io
    import tempfile

    # Try Whisper first (much better accuracy for brand names)
    if WHISPER_AVAILABLE:
        try:
            # Whisper needs a file, so save to temp file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
                temp_audio.write(audio_bytes)
                temp_audio.flush()

                # Load model and transcribe
                model = _load_whisper_model()
                result = model.transcribe(
                    temp_audio.name,
                    language="en",  # Specify English for better accuracy
                    task="transcribe",
                    fp16=False  # Use FP32 for CPU compatibility
                )

                # Clean up temp file
                import os
                os.unlink(temp_audio.name)

                return result["text"].strip()

        except Exception as whisper_error:
            st.warning(f"⚠️ Whisper transcription failed: {whisper_error}")
            st.info("💡 Falling back to Google Speech Recognition...")

    # Fallback to Google Speech Recognition
    if SPEECH_RECOGNITION_AVAILABLE:
        try:
            recognizer = sr.Recognizer()

            with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
                audio_data = recognizer.record(source)
                text = recognizer.recognize_google(audio_data)
                return text
        except Exception as e:
            st.error(f"Google Speech Recognition error: {e}")
            return None

    st.error("❌ No transcription service available. Install Whisper with: `pip install openai-whisper`")
    return None


def transcribe_audio_file(audio_file):
    """
    Transcribe audio from uploaded file using OpenAI Whisper (preferred) or Google Speech as fallback.
    """
    import io
    import tempfile

    # Read audio file
    audio_file.seek(0)
    audio_bytes = audio_file.read()

    # Try Whisper first (much better accuracy)
    if WHISPER_AVAILABLE:
        try:
            # Whisper can work with various audio formats
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
                temp_audio.write(audio_bytes)
                temp_audio.flush()

                # Load model and transcribe
                model = _load_whisper_model()
                result = model.transcribe(
                    temp_audio.name,
                    language="en",
                    task="transcribe",
                    fp16=False
                )

                # Clean up temp file
                import os
                os.unlink(temp_audio.name)

                return result["text"].strip()

        except Exception as whisper_error:
            st.warning(f"⚠️ Whisper transcription failed: {whisper_error}")
            st.info("💡 Falling back to Google Speech Recognition...")

    # Fallback to Google Speech Recognition
    if SPEECH_RECOGNITION_AVAILABLE:
        try:
            recognizer = sr.Recognizer()
            audio_file.seek(0)

            with sr.AudioFile(audio_file) as source:
                audio_data = recognizer.record(source)
                text = recognizer.recognize_google(audio_data)
                return text
        except Exception as e:
            st.error(f"Google Speech Recognition error: {e}")
            return None

    st.error("❌ No transcription service available. Install Whisper with: `pip install openai-whisper`")
    return None
