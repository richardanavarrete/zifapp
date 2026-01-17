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
    from audio_recorder_streamlit import audio_recorder
    AUDIO_RECORDER_AVAILABLE = True
except ImportError:
    AUDIO_RECORDER_AVAILABLE = False

# Speech recognition for file upload
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False

from models import VoiceCountSession, VoiceCountRecord
from voice_matcher import VoiceItemMatcher
from voice_export import export_voice_count_to_excel, get_inventory_order_from_template, get_default_inventory_order
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
    """Render browser-based voice recording interface."""
    if not AUDIO_RECORDER_AVAILABLE:
        st.warning("⚠️ Audio recorder not available. Install with: `pip install audio-recorder-streamlit`")
        st.info("💡 Use Manual Entry or Upload Audio File instead")
        return

    st.markdown("Click the microphone to start/stop recording. Speak clearly: 'Item name' then 'quantity'")

    # Record audio
    audio_bytes = audio_recorder(
        text="Click to record",
        recording_color="#e74c3c",
        neutral_color="#3498db",
        icon_size="2x",
        key="voice_recorder"
    )

    if audio_bytes:
        st.audio(audio_bytes, format="audio/wav")

        if st.button("🔄 Transcribe & Match", key="transcribe_btn"):
            with st.spinner("Transcribing..."):
                transcript = transcribe_audio_bytes(audio_bytes)
                if transcript:
                    st.success(f"Heard: {transcript}")
                    process_transcript(session, transcript, dataset)
                    st.rerun()
                else:
                    st.error("Could not transcribe audio. Please try again.")


def render_audio_file_input(session, dataset):
    """Render audio file upload interface."""
    if not SPEECH_RECOGNITION_AVAILABLE:
        st.warning("⚠️ Speech recognition not available. Install with: `pip install SpeechRecognition`")
        st.info("💡 Use Manual Entry or Browser Voice Recording instead")
        return

    st.markdown("Upload an audio file (WAV, MP3, FLAC) to transcribe")

    audio_file = st.file_uploader(
        "Upload Audio",
        type=['wav', 'mp3', 'flac', 'm4a'],
        key="audio_file_uploader"
    )

    if audio_file:
        st.audio(audio_file)

        if st.button("🔄 Transcribe & Match", key="file_transcribe_btn"):
            with st.spinner("Transcribing..."):
                transcript = transcribe_audio_file(audio_file)
                if transcript:
                    st.success(f"Transcribed: {transcript}")
                    process_transcript(session, transcript, dataset)
                    st.rerun()
                else:
                    st.error("Could not transcribe audio. Please try speaking more clearly.")


def process_transcript(session, transcript, dataset):
    """Process a transcript and add to session."""
    matcher = st.session_state.voice_matcher

    # Parse item name and count
    matches, count_value = matcher.match_with_count(transcript)

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
            is_verified=False
        )
        session.add_record(record)
        st.warning(f"⚠️ No match found for: '{transcript}'. Added to log for manual review.")
    else:
        # Show top match for confirmation
        top_match = matches[0]
        item = dataset.items[top_match.item_id]

        # Auto-verify high confidence matches
        if top_match.confidence >= 0.85:
            record = VoiceCountRecord(
                record_id=str(uuid.uuid4()),
                session_id=session.session_id,
                timestamp=datetime.now(),
                raw_transcript=transcript,
                cleaned_transcript=transcript,
                matched_item_id=top_match.item_id,
                count_value=count_value,
                confidence_score=top_match.confidence,
                match_method=top_match.method,
                is_verified=True
            )
            session.add_record(record)
            st.success(f"✓ Matched: {item.display_name} - Count: {count_value} (Confidence: {top_match.confidence:.0%})")
        else:
            # Show confirmation dialog for lower confidence
            st.session_state.pending_match = {
                'transcript': transcript,
                'matches': matches,
                'count_value': count_value
            }


def render_transcript_log(session, dataset):
    """Render the transcript log editor."""
    st.markdown("### 📋 Transcript Log")

    if not session.records:
        st.info("No records yet. Start counting above!")
        return

    # Convert records to DataFrame for editing
    log_data = []
    for record in session.records:
        item_name = ""
        if record.matched_item_id and record.matched_item_id in dataset.items:
            item_name = dataset.items[record.matched_item_id].display_name

        log_data.append({
            'Time': record.timestamp.strftime('%H:%M:%S'),
            'Transcript': record.cleaned_transcript or record.raw_transcript,
            'Matched Item': item_name,
            'Count': record.count_value,
            'Confidence': f"{record.confidence_score:.0%}",
            'Verified': "✓" if record.is_verified else "",
            'record_id': record.record_id  # Hidden column for tracking
        })

    df = pd.DataFrame(log_data)

    # Display as editable table
    st.dataframe(
        df[['Time', 'Transcript', 'Matched Item', 'Count', 'Confidence', 'Verified']],
        use_container_width=True,
        hide_index=True
    )

    # Action buttons
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("✓ Verify All", use_container_width=True):
            for record in session.records:
                if record.matched_item_id:
                    record.is_verified = True
            session.updated_at = datetime.now()
            st.success("All matched records verified!")
            st.rerun()

    with col2:
        if st.button("🔄 Re-match All", use_container_width=True):
            rematch_all_records(session, dataset)
            st.success("Re-matched all records!")
            st.rerun()

    with col3:
        if st.button("🗑️ Clear All", use_container_width=True):
            if st.session_state.get('confirm_clear', False):
                session.records = []
                session.total_items_counted = 0
                session.updated_at = datetime.now()
                st.session_state.confirm_clear = False
                st.success("All records cleared!")
                st.rerun()
            else:
                st.session_state.confirm_clear = True
                st.warning("Click again to confirm deletion")

    with col4:
        # Download transcript as text
        transcript_text = "\n".join([
            f"{r.timestamp.strftime('%H:%M:%S')} - {r.raw_transcript} -> {r.matched_item_id or 'UNMATCHED'} ({r.count_value})"
            for r in session.records
        ])
        st.download_button(
            "📄 Download Log",
            data=transcript_text,
            file_name=f"transcript_{session.session_name}.txt",
            mime="text/plain",
            use_container_width=True
        )


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
            matches, count_value = matcher.match_with_count(record.raw_transcript)
            if matches:
                top_match = matches[0]
                record.matched_item_id = top_match.item_id
                record.confidence_score = top_match.confidence
                record.match_method = top_match.method
                if count_value is not None:
                    record.count_value = count_value
                # Auto-verify high confidence
                if top_match.confidence >= 0.85:
                    record.is_verified = True

    session.updated_at = datetime.now()


def transcribe_audio_bytes(audio_bytes):
    """Transcribe audio from bytes using speech recognition."""
    if not SPEECH_RECOGNITION_AVAILABLE:
        return None

    try:
        import io
        from pydub import AudioSegment

        # Convert bytes to AudioSegment
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))

        # Export as WAV for speech recognition
        wav_io = io.BytesIO()
        audio.export(wav_io, format='wav')
        wav_io.seek(0)

        # Recognize speech
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_io) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)
            return text
    except Exception as e:
        st.error(f"Transcription error: {e}")
        return None


def transcribe_audio_file(audio_file):
    """Transcribe audio from uploaded file."""
    if not SPEECH_RECOGNITION_AVAILABLE:
        return None

    try:
        recognizer = sr.Recognizer()

        # Read audio file
        audio_file.seek(0)
        with sr.AudioFile(audio_file) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)
            return text
    except Exception as e:
        st.error(f"Transcription error: {e}")
        return None
