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
        ["💬 Manual Entry", "🎤 Voice Recording (Browser)", "📁 Upload Audio File", "⚖️ Weigh Bottle/Keg", "📷 Photo Count"],
        horizontal=True
    )

    if input_method == "💬 Manual Entry":
        render_manual_input(session, dataset)
    elif input_method == "🎤 Voice Recording (Browser)":
        render_browser_voice_input(session, dataset)
    elif input_method == "📁 Upload Audio File":
        render_audio_file_input(session, dataset)
    elif input_method == "⚖️ Weigh Bottle/Keg":
        render_weight_input(session, dataset)
    elif input_method == "📷 Photo Count":
        render_photo_counting(session, dataset)

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


def render_weight_input(session, dataset):
    """Render weight-based counting interface."""
    from bottle_weights import format_weight_display, get_weight_ranges

    st.markdown("### ⚖️ Weigh Bottle/Keg")
    st.info("📏 Place item on scale and read weight. **Bottles in grams, kegs in pounds.**")

    # Initialize session state for weight workflow
    if 'weight_selected_item_id' not in st.session_state:
        st.session_state.weight_selected_item_id = None

    # Step 1: Search and select item
    st.markdown("**Step 1: What item are you weighing?**")

    col1, col2 = st.columns([4, 1])
    with col1:
        item_search = st.text_input(
            "Item name",
            placeholder="Type item name or use voice...",
            key="weight_item_search"
        )

    # Show fuzzy matches
    if item_search:
        matcher = st.session_state.voice_matcher
        matches = matcher.match(item_search, top_n=5)

        if matches:
            st.markdown("**Select item:**")
            for match in matches:
                item = dataset.items[match.item_id]
                col_a, col_b, col_c = st.columns([3, 1, 1])
                with col_a:
                    if st.button(
                        f"{item.display_name}",
                        key=f"weight_select_{match.item_id}",
                        use_container_width=True
                    ):
                        st.session_state.weight_selected_item_id = match.item_id
                        st.rerun()
                with col_b:
                    st.caption(f"{match.confidence:.0%}")
                with col_c:
                    unit_type = "Keg" if item.is_keg() else "Bottle"
                    st.caption(unit_type)

    # Step 2: Input weight
    if st.session_state.weight_selected_item_id:
        item = dataset.items[st.session_state.weight_selected_item_id]

        st.markdown("---")
        st.success(f"✓ Selected: **{item.display_name}**")

        # Determine if keg or bottle
        is_keg_item = item.is_keg()
        weight_unit = "pounds" if is_keg_item else "grams"
        weight_label = "Weight (pounds)" if is_keg_item else "Weight (grams)"

        # Get expected weight range
        ranges = get_weight_ranges(item.unit_of_measure or "Bottle")
        min_weight, max_weight = ranges['pounds'] if is_keg_item else ranges['grams']

        st.markdown(f"**Step 2: Place on scale and read weight in {weight_unit}:**")
        st.caption(f"Expected range: {min_weight:.0f} - {max_weight:.0f} {weight_unit}")

        weight_input = st.number_input(
            weight_label,
            min_value=0.0,
            max_value=max_weight * 2,
            step=10.0 if not is_keg_item else 1.0,
            format="%.1f" if is_keg_item else "%.0f",
            key="weight_input_value"
        )

        # Calculate fill level
        if weight_input > 0:
            fill_pct = item.calculate_fill_from_weight(
                weight_input,
                input_unit=weight_unit
            )

            st.markdown("---")
            st.markdown("**Fill Level:**")

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Percentage", f"{fill_pct:.0%}")
            with col2:
                st.metric("Bottle Count", f"{fill_pct:.2f}")

            # Visual progress bar
            if fill_pct > 0.5:
                progress_color = "🟢"
            elif fill_pct > 0.25:
                progress_color = "🟡"
            else:
                progress_color = "🔴"

            st.progress(fill_pct)
            st.caption(f"{progress_color} {weight_input} {weight_unit} = {fill_pct:.0%} full")

            # Validation warnings
            if weight_input < min_weight * 0.8 or weight_input > max_weight * 1.2:
                st.warning(f"⚠️ Weight outside expected range. Please verify reading.")

            # Add to session button
            if st.button("✓ Add to Session", type="primary", use_container_width=True):
                record = VoiceCountRecord(
                    record_id=str(uuid.uuid4()),
                    session_id=session.session_id,
                    timestamp=datetime.now(),
                    raw_transcript=f"Weighed: {weight_input} {weight_unit}",
                    matched_item_id=item.item_id,
                    count_value=fill_pct,
                    confidence_score=1.0,  # Weight is precise
                    match_method="weight",
                    is_verified=True,
                    notes=f"{weight_input} {weight_unit} = {fill_pct:.0%} full"
                )
                session.add_record(record)
                st.session_state.weight_selected_item_id = None
                storage.save_voice_count_session(session)
                st.success(f"✓ Added {fill_pct:.2f} bottles of {item.display_name}")
                st.rerun()

    # Clear selection button
    if st.session_state.weight_selected_item_id:
        if st.button("← Start Over", key="weight_clear"):
            st.session_state.weight_selected_item_id = None
            st.rerun()


def render_photo_counting(session, dataset):
    """Render photo-based counting interface (WISK-style visual mode)."""
    st.markdown("### 📷 Photo Count")
    st.info("📸 Take a photo of your shelf, tap each bottle, then specify fill level and depth.")

    # Try to use streamlit-drawable-canvas for annotation
    try:
        from streamlit_drawable_canvas import st_canvas
        from PIL import Image
        CANVAS_AVAILABLE = True
    except ImportError:
        CANVAS_AVAILABLE = False
        st.error("⚠️ Photo counting requires streamlit-drawable-canvas. Install with: `pip install streamlit-drawable-canvas`")
        st.info("For now, use other counting methods (Manual, Voice, or Weight)")
        return

    # Initialize session state
    if 'photo_bottles' not in st.session_state:
        st.session_state.photo_bottles = []
    if 'photo_image' not in st.session_state:
        st.session_state.photo_image = None

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
        photo = st.camera_input("Take photo of shelf")
    else:
        photo = st.file_uploader("Upload photo", type=['jpg', 'jpeg', 'png'], key="photo_upload")

    if photo:
        # Load image
        image = Image.open(photo)
        st.session_state.photo_image = image

        st.markdown("---")
        st.markdown("**Step 2: Tap each bottle on the image**")
        st.caption("Click/tap bottles to mark them. Each click adds a numbered marker.")

        # Create canvas for annotation
        canvas_result = st_canvas(
            fill_color="rgba(255, 165, 0, 0.3)",
            stroke_width=2,
            stroke_color="#FF6B6B",
            background_image=image,
            drawing_mode="point",
            point_display_radius=15,
            height=min(image.height, 600),
            width=min(image.width, 800),
            key="photo_canvas",
        )

        # Get clicked points
        if canvas_result.json_data is not None:
            objects = canvas_result.json_data.get("objects", [])

            if len(objects) > 0:
                st.markdown("---")
                st.markdown(f"**Step 3: Specify details for each bottle ({len(objects)} marked)**")

                # Process each marked bottle
                for i, obj in enumerate(objects):
                    with st.expander(f"🍾 Bottle #{i+1} (x: {obj['left']:.0f}, y: {obj['top']:.0f})", expanded=(i==0)):
                        col1, col2 = st.columns([3, 1])

                        with col1:
                            item_name = st.text_input(
                                "What is this?",
                                placeholder="Type item name...",
                                key=f"photo_item_{i}"
                            )

                        # Fuzzy match if searching
                        matched_item_id = None
                        if item_name:
                            matcher = st.session_state.voice_matcher
                            matches = matcher.match(item_name, top_n=3)
                            if matches:
                                st.markdown("**Select:**")
                                for match in matches:
                                    if st.button(
                                        f"{dataset.items[match.item_id].display_name} ({match.confidence:.0%})",
                                        key=f"photo_match_{i}_{match.item_id}"
                                    ):
                                        matched_item_id = match.item_id

                        # Fill level selector
                        fill_level = st.select_slider(
                            "Fill level",
                            options=["Empty", "1/4", "1/2", "3/4", "Full"],
                            value="Full",
                            key=f"photo_fill_{i}"
                        )

                        # Depth (how many deep on shelf)
                        depth = st.number_input(
                            "How many bottles deep?",
                            min_value=1,
                            max_value=20,
                            value=1,
                            key=f"photo_depth_{i}"
                        )

                        # Calculate count
                        fill_map = {"Empty": 0.0, "1/4": 0.25, "1/2": 0.5, "3/4": 0.75, "Full": 1.0}
                        fill_pct = fill_map[fill_level]
                        total_count = depth * fill_pct

                        st.info(f"📊 Total: {total_count:.2f} bottles ({depth} deep × {fill_pct:.0%} full)")

                        # Store in session state
                        bottle_data = {
                            'index': i,
                            'item_name': item_name,
                            'matched_item_id': matched_item_id,
                            'fill_level': fill_pct,
                            'depth': depth,
                            'count': total_count,
                            'position': (obj['left'], obj['top'])
                        }

                        # Update session state
                        if i < len(st.session_state.photo_bottles):
                            st.session_state.photo_bottles[i] = bottle_data
                        else:
                            st.session_state.photo_bottles.append(bottle_data)

                # Add all to session button
                st.markdown("---")
                if st.button("✓ Add All Bottles to Session", type="primary", use_container_width=True):
                    added_count = 0
                    for bottle_data in st.session_state.photo_bottles:
                        if bottle_data.get('matched_item_id'):
                            record = VoiceCountRecord(
                                record_id=str(uuid.uuid4()),
                                session_id=session.session_id,
                                timestamp=datetime.now(),
                                raw_transcript=f"Photo: {bottle_data['item_name']}",
                                matched_item_id=bottle_data['matched_item_id'],
                                count_value=bottle_data['count'],
                                confidence_score=0.95,  # User confirmed
                                match_method="photo",
                                is_verified=True,
                                notes=f"{bottle_data['fill_level']:.0%} full, {bottle_data['depth']} deep"
                            )
                            session.add_record(record)
                            added_count += 1

                    if added_count > 0:
                        storage.save_voice_count_session(session)
                        st.session_state.photo_bottles = []
                        st.session_state.photo_image = None
                        st.success(f"✓ Added {added_count} bottles to session!")
                        st.rerun()
                    else:
                        st.warning("⚠️ No matched items to add. Please identify bottles first.")


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
