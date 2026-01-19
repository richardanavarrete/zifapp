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

# OpenAI for AI-powered photo counting
try:
    from openai import OpenAI
    import base64
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

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
    st.info("💡 **Tip**: You can also input weights! Say \"Buffalo Trace 850 grams\" or \"Keg 65 pounds\"")

    input_method = st.radio(
        "Input Method",
        ["💬 Manual Entry", "🎤 Voice Recording (Browser)", "📁 Upload Audio File", "📷 Photo Count", "⚖️ Scale Photo"],
        horizontal=True
    )

    if input_method == "💬 Manual Entry":
        render_manual_input(session, dataset)
    elif input_method == "🎤 Voice Recording (Browser)":
        render_browser_voice_input(session, dataset)
    elif input_method == "📁 Upload Audio File":
        render_audio_file_input(session, dataset)
    elif input_method == "📷 Photo Count":
        render_photo_counting(session, dataset)
    elif input_method == "⚖️ Scale Photo":
        render_scale_photo(session, dataset)

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

    st.markdown("**🎤 Continuous Recording Mode**")
    st.info("💡 Click microphone to start/stop. Say multiple items: 'Buffalo Trace 3, Titos 5, Makers 850 grams...'")

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

        if st.button("🔄 Transcribe & Process All Items", key="transcribe_btn", type="primary"):
            with st.spinner("Transcribing..."):
                transcript = transcribe_audio_bytes(audio_bytes)
                if transcript:
                    st.success(f"📝 Transcribed: {transcript}")

                    # Process multiple items from single transcript
                    items_processed = process_multi_item_transcript(session, transcript, dataset)

                    if items_processed > 0:
                        st.success(f"✅ Added {items_processed} items to session!")
                        st.rerun()
                    else:
                        st.warning("⚠️ No items could be matched. Try speaking more clearly.")
                else:
                    st.error("Could not transcribe audio. Please try again.")


def render_audio_file_input(session, dataset):
    """Render audio file upload interface."""
    if not SPEECH_RECOGNITION_AVAILABLE:
        st.warning("⚠️ Speech recognition not available. Install with: `pip install SpeechRecognition`")
        st.info("💡 Use Manual Entry or Browser Voice Recording instead")
        return

    st.markdown("**📁 Upload Audio File**")
    st.info("💡 Upload a recording with multiple items: 'Buffalo Trace 3, Titos 5, Makers 850 grams...'")

    audio_file = st.file_uploader(
        "Upload Audio",
        type=['wav', 'mp3', 'flac', 'm4a'],
        key="audio_file_uploader"
    )

    if audio_file:
        st.audio(audio_file)

        if st.button("🔄 Transcribe & Process All Items", key="file_transcribe_btn", type="primary"):
            with st.spinner("Transcribing..."):
                transcript = transcribe_audio_file(audio_file)
                if transcript:
                    st.success(f"📝 Transcribed: {transcript}")

                    # Process multiple items from single transcript
                    items_processed = process_multi_item_transcript(session, transcript, dataset)

                    if items_processed > 0:
                        st.success(f"✅ Added {items_processed} items to session!")
                        st.rerun()
                    else:
                        st.warning("⚠️ No items could be matched. Try speaking more clearly.")
                else:
                    st.error("Could not transcribe audio. Please try speaking more clearly.")


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


def render_photo_counting(session, dataset):
    """Render AI-powered photo counting interface using GPT-4 Vision."""
    st.markdown("### 📷 AI Photo Count")
    st.info("📸 Take a photo of your shelf and let AI identify and count bottles automatically.")

    # Check if OpenAI is available
    if not OPENAI_AVAILABLE:
        st.error("⚠️ AI photo counting requires OpenAI package. Install with: `pip install openai`")
        st.info("For now, use other counting methods (Manual, Voice, or Weight)")
        return

    # Check if API key is configured
    if "openai" not in st.secrets or "api_key" not in st.secrets["openai"]:
        st.error("⚠️ OpenAI API key not configured")
        st.info("Please add your API key to .streamlit/secrets.toml")
        st.code('''[openai]\napi_key = "your-api-key-here"''', language="toml")
        return

    from PIL import Image

    # Initialize session state
    if 'ai_analysis_result' not in st.session_state:
        st.session_state.ai_analysis_result = None
    if 'ai_detected_items' not in st.session_state:
        st.session_state.ai_detected_items = []

    # Step 1: Capture or upload photo
    st.markdown("**Step 1: Take or upload photo**")

    photo_input_method = st.radio(
        "Photo source",
        ["📷 Camera", "📁 Upload"],
        horizontal=True,
        key="photo_source"
    )

    photo = None
    if photo_input_method == "📷 Camera":
        photo = st.camera_input("Take photo of shelf", key="camera_input")
    else:
        photo = st.file_uploader("Upload photo", type=['jpg', 'jpeg', 'png'], key="photo_upload")

    if photo:
        # Load image
        image = Image.open(photo)

        # Convert to RGB mode
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Display the photo
        st.image(image, caption="Your photo", use_container_width=True)

        # Clear previous analysis if new photo is taken
        photo_hash = hash(photo.getvalue())
        if 'last_photo_hash' not in st.session_state or st.session_state.last_photo_hash != photo_hash:
            st.session_state.ai_analysis_result = None
            st.session_state.ai_detected_items = []
            st.session_state.last_photo_hash = photo_hash

        st.markdown("---")
        st.markdown("**Step 2: Analyze with AI**")

        # Analyze button
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("🤖 Analyze Photo with AI", type="primary", use_container_width=True):
                with st.spinner("🔍 Analyzing photo..."):
                    ai_result = analyze_photo_with_ai(image)
                    if ai_result:
                        st.session_state.ai_analysis_result = ai_result
                        st.rerun()
        with col2:
            if st.button("❌ Clear", use_container_width=True):
                st.session_state.ai_analysis_result = None
                st.session_state.ai_detected_items = []
                if 'last_photo_hash' in st.session_state:
                    del st.session_state.last_photo_hash
                st.rerun()

        # Show AI results if available
        if st.session_state.ai_analysis_result:
            st.markdown("---")
            st.markdown("**Step 3: AI Detected Items**")

            # Display raw AI response
            st.markdown("**AI Analysis:**")
            st.info(st.session_state.ai_analysis_result)

            # Process the AI response as if it's a transcript
            st.markdown("---")
            st.markdown("**Step 4: Confirm and Add**")

            if st.button("✓ Process AI Results", type="primary", use_container_width=True):
                # Convert AI format (2x Product) to transcript format (Product 2)
                transcript = convert_ai_format_to_transcript(st.session_state.ai_analysis_result)

                # Use existing multi-item processing
                with st.spinner("Processing AI detected items..."):
                    items_processed = process_multi_item_transcript(session, transcript, dataset)

                if items_processed > 0:
                    st.success(f"✓ Added {items_processed} items from AI analysis!")
                    st.session_state.ai_analysis_result = None
                    st.session_state.ai_detected_items = []
                    st.rerun()
                else:
                    st.warning("⚠️ No items could be matched. Please try voice or manual counting.")


def convert_ai_format_to_transcript(ai_response):
    """
    Convert AI photo analysis format to voice transcript format.

    AI format: "- 2x Tito's Vodka\n- 1x Buffalo Trace"
    Transcript format: "Tito's Vodka 2, Buffalo Trace 1"

    Args:
        ai_response: AI analysis text

    Returns:
        str: Converted transcript
    """
    import re

    # Extract lines with format "Nx Product Name" or "N x Product Name"
    # Matches: "2x Tito's Vodka", "1x Buffalo Trace", "3 x Jagermeister"
    pattern = r'[-•]\s*(\d+)\s*x\s+(.+?)(?=\n|$)'

    matches = re.findall(pattern, ai_response, re.IGNORECASE | re.MULTILINE)

    # Convert to "Product N, Product N" format
    items = []
    for count, product in matches:
        # Clean up product name (remove trailing punctuation, extra spaces)
        product = product.strip().rstrip('.,;')
        items.append(f"{product} {count}")

    return ', '.join(items)


def render_scale_photo(session, dataset):
    """Render AI-powered scale photo interface for bottle weighing."""
    st.markdown("### ⚖️ Scale Photo")
    st.info("📸 Position bottle on scale with label visible. AI will read both the label and weight!")

    # Check if OpenAI is available
    if not OPENAI_AVAILABLE:
        st.error("⚠️ AI scale photo requires OpenAI package. Install with: `pip install openai`")
        st.info("For now, use other counting methods (Manual or Voice)")
        return

    # Check if API key is configured
    if "openai" not in st.secrets or "api_key" not in st.secrets["openai"]:
        st.error("⚠️ OpenAI API key not configured")
        st.info("Please add your API key to .streamlit/secrets.toml")
        st.code('''[openai]\napi_key = "your-api-key-here"''', language="toml")
        return

    from PIL import Image

    # Initialize session state
    if 'scale_analysis_result' not in st.session_state:
        st.session_state.scale_analysis_result = None
    if 'scale_photo_count' not in st.session_state:
        st.session_state.scale_photo_count = 0

    st.markdown("**Quick Workflow:**")
    st.caption("1. Place bottle on scale (label facing camera) → 2. Take photo → 3. Remove bottle → 4. Repeat!")

    # Photo input
    photo = st.camera_input("📷 Capture bottle on scale", key=f"scale_camera_{st.session_state.scale_photo_count}")

    if photo:
        # Load image
        image = Image.open(photo)

        # Convert to RGB mode
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Display the photo in a smaller size
        col1, col2 = st.columns([2, 1])
        with col1:
            st.image(image, caption="Bottle on scale", use_container_width=True)

        with col2:
            if st.button("🤖 Analyze", type="primary", use_container_width=True, key="analyze_scale"):
                with st.spinner("🔍 Reading label and scale..."):
                    ai_result = analyze_scale_photo_with_ai(image)
                    if ai_result:
                        st.session_state.scale_analysis_result = ai_result
                        st.rerun()

        # Show AI results if available
        if st.session_state.scale_analysis_result:
            st.markdown("---")
            st.markdown("**AI Analysis:**")
            st.success(st.session_state.scale_analysis_result)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Add to Session", type="primary", use_container_width=True):
                    # Process the result as a transcript
                    transcript = st.session_state.scale_analysis_result

                    with st.spinner("Adding item..."):
                        # Use single item processing (not multi-item)
                        process_transcript(session, transcript, dataset)

                    st.success("✓ Item added!")
                    st.session_state.scale_analysis_result = None
                    st.session_state.scale_photo_count += 1
                    st.rerun()

            with col2:
                if st.button("❌ Skip", use_container_width=True):
                    st.session_state.scale_analysis_result = None
                    st.session_state.scale_photo_count += 1
                    st.rerun()

        # Show photo counter
        if st.session_state.scale_photo_count > 0:
            st.caption(f"📊 Bottles processed this session: {st.session_state.scale_photo_count}")


def analyze_scale_photo_with_ai(image):
    """
    Analyze a photo of a bottle on a scale using GPT-4 Vision.
    Extracts both the bottle label and weight reading.

    Args:
        image: PIL Image object

    Returns:
        str: AI response with bottle name and weight (e.g., "Tito's Vodka 850 grams")
    """
    if not OPENAI_AVAILABLE:
        st.error("⚠️ OpenAI package not installed")
        return None

    if "openai" not in st.secrets or "api_key" not in st.secrets["openai"]:
        st.error("⚠️ OpenAI API key not configured")
        return None

    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=st.secrets["openai"]["api_key"])

        # Convert PIL image to base64
        import io
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

        # Create the API request
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """You are analyzing a photo of a liquor bottle placed on a digital scale.

Your task:
1. Read the bottle label - identify the brand and product name (e.g., "Tito's Vodka", "Buffalo Trace Bourbon", "Corona Extra")
2. Read the scale display - extract the weight in grams or pounds

Respond in this EXACT format:
[Brand Name] [Product Type] [weight] [unit]

Examples:
- "Tito's Vodka 850 grams"
- "Buffalo Trace Bourbon 1.2 pounds"
- "Corona Extra 645 grams"

If you cannot read the bottle label, say "Unknown Bottle [weight] [unit]"
If you cannot read the scale, say "Could not read scale display"

Be concise - just give the brand, product, weight, and unit."""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=100
        )

        return response.choices[0].message.content

    except Exception as e:
        st.error(f"❌ Error analyzing photo: {str(e)}")
        return None


def analyze_photo_with_ai(image):
    """
    Analyze a photo using GPT-4 Vision to identify and count bottles.

    Args:
        image: PIL Image object

    Returns:
        str: AI response describing bottles found in the image, or None if error
    """
    if not OPENAI_AVAILABLE:
        st.error("⚠️ OpenAI package not installed. Install with: `pip install openai`")
        return None

    # Check if API key is configured
    if "openai" not in st.secrets or "api_key" not in st.secrets["openai"]:
        st.error("⚠️ OpenAI API key not configured. Please add it to .streamlit/secrets.toml")
        return None

    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=st.secrets["openai"]["api_key"])

        # Convert PIL image to base64
        import io
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

        # Create the API request
        response = client.chat.completions.create(
            model="gpt-4o",  # gpt-4o supports vision
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """Analyze this photo of a liquor shelf and list all bottles you can identify.

For each bottle, provide:
- Brand name and product type (e.g., "Tito's Vodka", "Buffalo Trace Bourbon")
- Approximate count of visible bottles of that same product

Format your response as a simple list like:
- 3x Tito's Vodka
- 2x Buffalo Trace Bourbon
- 1x Jagermeister

Only list bottles you can clearly identify. If you see bottles but can't read the label, describe them as "Unknown [type] bottle"."""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=500
        )

        return response.choices[0].message.content

    except Exception as e:
        st.error(f"❌ Error analyzing photo: {str(e)}")
        return None


def process_multi_item_transcript(session, transcript, dataset):
    """
    Process multiple items from a continuous recording transcript.

    Example input: "Buffalo Trace 3, Titos 5, Makers Mark 850 grams, Jim Beam 2"

    Args:
        session: Current VoiceCountSession
        transcript: Full transcript containing multiple items
        dataset: InventoryDataset

    Returns:
        Number of items successfully processed
    """
    matcher = st.session_state.voice_matcher

    # Split transcript by common separators (comma, "and", semicolon)
    # Also handle natural pauses that might be transcribed as periods
    separators = [',', ' and ', ';', '.']

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


def transcribe_audio_bytes(audio_bytes):
    """Transcribe audio from bytes using speech recognition."""
    if not SPEECH_RECOGNITION_AVAILABLE:
        return None

    try:
        import io

        recognizer = sr.Recognizer()

        # The audio-recorder-streamlit outputs WAV format by default
        # Try direct recognition first (no conversion needed)
        try:
            with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
                audio_data = recognizer.record(source)
                text = recognizer.recognize_google(audio_data)
                return text
        except Exception as direct_error:
            # If direct recognition fails, try with pydub conversion
            try:
                from pydub import AudioSegment

                # Convert bytes to AudioSegment
                audio = AudioSegment.from_file(io.BytesIO(audio_bytes))

                # Export as WAV for speech recognition
                wav_io = io.BytesIO()
                audio.export(wav_io, format='wav')
                wav_io.seek(0)

                # Recognize speech
                with sr.AudioFile(wav_io) as source:
                    audio_data = recognizer.record(source)
                    text = recognizer.recognize_google(audio_data)
                    return text
            except Exception as conversion_error:
                st.error(f"Could not transcribe audio. FFmpeg may not be installed. Error: {conversion_error}")
                st.info("💡 Tip: Use Manual Entry mode as a fallback, or check that FFmpeg is installed.")
                return None
    except Exception as e:
        st.error(f"Transcription error: {e}")
        return None


def transcribe_audio_file(audio_file):
    """Transcribe audio from uploaded file."""
    if not SPEECH_RECOGNITION_AVAILABLE:
        return None

    try:
        import io
        recognizer = sr.Recognizer()

        # Read audio file
        audio_file.seek(0)
        audio_bytes = audio_file.read()

        # Try direct recognition first
        try:
            audio_file.seek(0)
            with sr.AudioFile(audio_file) as source:
                audio_data = recognizer.record(source)
                text = recognizer.recognize_google(audio_data)
                return text
        except Exception as direct_error:
            # If direct recognition fails, try with pydub conversion
            try:
                from pydub import AudioSegment

                # Convert to WAV format
                audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
                wav_io = io.BytesIO()
                audio.export(wav_io, format='wav')
                wav_io.seek(0)

                with sr.AudioFile(wav_io) as source:
                    audio_data = recognizer.record(source)
                    text = recognizer.recognize_google(audio_data)
                    return text
            except Exception as conversion_error:
                st.error(f"Could not transcribe audio file. FFmpeg may not be installed. Error: {conversion_error}")
                st.info("💡 Tip: Try using WAV format, or use Manual Entry mode as a fallback.")
                return None
    except Exception as e:
        st.error(f"Transcription error: {e}")
        return None
