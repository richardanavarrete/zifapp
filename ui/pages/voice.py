"""Voice Counting Page."""

import streamlit as st
import pandas as pd
from datetime import datetime

from ui.api_client import get_client


def render():
    """Render the voice counting page."""
    st.title("Voice Counting")

    # Tabs
    tab1, tab2, tab3 = st.tabs(["Count", "Sessions", "Export"])

    with tab1:
        render_counting_section()

    with tab2:
        render_sessions_section()

    with tab3:
        render_export_section()


def render_counting_section():
    """Render the main counting interface."""
    st.subheader("Voice Inventory Count")

    client = get_client()

    # Session management
    col1, col2 = st.columns([2, 1])

    with col1:
        # Load or create session
        sessions_result = client.list_sessions(status="in_progress")
        sessions = sessions_result.data if sessions_result.success and sessions_result.data else []

        session_options = ["Create New Session"] + [
            f"{s.get('session_name', s.get('session_id', ''))}"
            for s in sessions
        ]

        selected_session = st.selectbox(
            "Session",
            options=session_options,
            index=0,
        )

    with col2:
        if selected_session == "Create New Session":
            new_session_name = st.text_input(
                "Session Name",
                value=f"Count {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            location = st.text_input("Location (optional)")

            if st.button("Create Session"):
                result = client.create_session(
                    session_name=new_session_name,
                    location=location if location else None,
                )
                if result.success:
                    st.session_state['current_session'] = result.data
                    st.success("Session created!")
                    st.rerun()
                else:
                    st.error(f"Failed to create session: {result.error}")
        else:
            # Load selected session
            session_idx = session_options.index(selected_session) - 1
            if 0 <= session_idx < len(sessions):
                st.session_state['current_session'] = sessions[session_idx]
                st.info(f"Session: {sessions[session_idx].get('session_name', 'Unknown')}")

    # Audio recording/upload
    st.divider()
    st.subheader("Record or Upload Audio")

    audio_file = st.file_uploader(
        "Upload audio file",
        type=["webm", "mp3", "wav", "m4a", "ogg"],
        help="Upload a recording of your inventory count"
    )

    if audio_file:
        st.audio(audio_file)

        col1, col2 = st.columns(2)
        with col1:
            remove_silence = st.checkbox("Remove silence", value=True)
        with col2:
            language = st.selectbox("Language", options=["en", "es"], index=0)

        if st.button("Transcribe", type="primary"):
            with st.spinner("Transcribing audio..."):
                result = client.transcribe_audio(
                    file_content=audio_file,
                    filename=audio_file.name,
                    language=language,
                    remove_silence=remove_silence,
                )

                if result.success:
                    st.session_state['transcription'] = result.data
                    st.success("Transcription complete!")
                else:
                    st.error(f"Transcription failed: {result.error}")

    # Manual text entry
    st.divider()
    st.subheader("Manual Entry")

    manual_text = st.text_area(
        "Enter count text",
        value=st.session_state.get('transcription', {}).get('text', ''),
        placeholder="e.g., buffalo trace 2 bottles, titos 3 bottles, jameson 1 bottle",
        height=100,
    )

    if st.button("Match Items"):
        if manual_text:
            with st.spinner("Matching items..."):
                session_id = st.session_state.get('current_session', {}).get('session_id')
                result = client.match_text(
                    text=manual_text,
                    session_id=session_id,
                )

                if result.success:
                    st.session_state['matches'] = result.data
                else:
                    st.error(f"Matching failed: {result.error}")

    # Display matches
    if 'matches' in st.session_state and st.session_state['matches']:
        display_matches(st.session_state['matches'])


def display_matches(match_data: dict):
    """Display matched items."""
    st.divider()
    st.subheader("Matched Items")

    matches = match_data.get('matches', [])
    unmatched = match_data.get('unmatched', [])

    if matches:
        for i, match in enumerate(matches):
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

                with col1:
                    matched_item = match.get('matched_item', {})
                    if matched_item:
                        st.write(f"**{matched_item.get('display_name', 'Unknown')}**")
                        st.caption(f"Confidence: {matched_item.get('confidence', 0):.0%}")
                    else:
                        st.write(f"*{match.get('raw_text', '')}*")
                        st.caption("No match found")

                with col2:
                    quantity = match.get('parsed_quantity', 1)
                    st.metric("Qty", quantity)

                with col3:
                    unit = match.get('parsed_unit', 'bottles')
                    st.write(unit)

                with col4:
                    if matched_item and match.get('is_confident_match'):
                        if st.button("Confirm", key=f"confirm_{i}"):
                            # Add to session
                            session_id = st.session_state.get('current_session', {}).get('session_id')
                            if session_id:
                                client = get_client()
                                client.add_record(
                                    session_id=session_id,
                                    raw_text=match.get('raw_text', ''),
                                    quantity=quantity,
                                    item_id=matched_item.get('item_id'),
                                    unit=unit,
                                    confirmed=True,
                                )
                                st.success("Added!")
                    else:
                        st.button("Review", key=f"review_{i}")

                st.divider()

    if unmatched:
        st.warning(f"Could not match {len(unmatched)} items")
        for item in unmatched:
            st.write(f"- {item}")


def render_sessions_section():
    """Render sessions list."""
    st.subheader("Counting Sessions")

    client = get_client()
    result = client.list_sessions()

    if not result.success:
        st.error(f"Failed to load sessions: {result.error}")
        return

    sessions = result.data if isinstance(result.data, list) else []

    if not sessions:
        st.info("No counting sessions yet. Start a new count above.")
        return

    df = pd.DataFrame(sessions)
    if 'created_at' in df.columns:
        df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M')

    columns = ['session_name', 'status', 'items_counted', 'total_units', 'created_at']
    available_cols = [c for c in columns if c in df.columns]

    st.dataframe(df[available_cols], use_container_width=True, hide_index=True)


def render_export_section():
    """Render export section."""
    st.subheader("Export Session Data")

    client = get_client()

    # Get sessions
    result = client.list_sessions(status="completed")
    sessions = result.data if result.success and result.data else []

    if not sessions:
        st.info("No completed sessions to export.")
        return

    selected_session = st.selectbox(
        "Select Session",
        options=[s.get('session_id', '') for s in sessions],
        format_func=lambda x: next(
            (s.get('session_name', x) for s in sessions if s.get('session_id') == x),
            x
        )
    )

    export_format = st.radio("Format", options=["JSON", "CSV"], horizontal=True)

    if st.button("Export"):
        result = client.export_session(
            session_id=selected_session,
            format=export_format.lower(),
        )

        if result.success:
            st.json(result.data)
            # TODO: Add download button
        else:
            st.error(f"Export failed: {result.error}")
