"""
Voice Counting Page

Transcribe audio, match to items, and export for copy/paste.
"""

import streamlit as st

from ui.api_client import APIClient


def render_voice_page(client: APIClient):
    """Render the voice counting page."""
    st.header("Voice Counting")
    st.markdown("Transcribe audio, match to inventory items, and export counts.")

    # Tabs for workflow
    tab_record, tab_sessions, tab_export = st.tabs(["Record/Upload", "Sessions", "Export"])

    with tab_record:
        render_recording_tab(client)

    with tab_sessions:
        render_sessions_tab(client)

    with tab_export:
        render_export_tab(client)


def render_recording_tab(client: APIClient):
    """Recording and transcription tab."""
    st.subheader("Record or Upload Audio")

    # Session selection/creation
    col1, col2 = st.columns([2, 1])
    with col1:
        session_name = st.text_input("Session Name", value="Count Session")
    with col2:
        if st.button("Create Session", type="primary"):
            result = client.post("/voice/sessions", params={"name": session_name})
            if result.get("session_id"):
                st.session_state["current_session"] = result
                st.success(f"Created session: {result['session_id']}")

    st.divider()

    # Audio upload
    st.subheader("Upload Audio")
    audio_file = st.file_uploader(
        "Upload audio file",
        type=["webm", "mp3", "wav", "m4a", "ogg"],
        help="Record on your phone or upload existing audio"
    )

    if audio_file:
        st.audio(audio_file)

        if st.button("Transcribe", type="primary"):
            with st.spinner("Transcribing..."):
                result = client.upload_file("/voice/transcribe", audio_file)

                if result and result.get("text"):
                    st.session_state["transcription"] = result
                    st.success("Transcription complete!")
                else:
                    st.error("Transcription failed")

    # Show transcription result
    if "transcription" in st.session_state:
        st.subheader("Transcription Result")
        result = st.session_state["transcription"]

        text = st.text_area(
            "Transcribed Text (edit if needed)",
            value=result.get("text", ""),
            height=150
        )

        # Dataset selection for matching
        datasets = client.get("/inventory/datasets") or []
        dataset_options = {d["name"]: d["dataset_id"] for d in datasets}

        selected_dataset = st.selectbox(
            "Match against dataset (optional)",
            options=["None"] + list(dataset_options.keys())
        )

        if st.button("Match Items", type="primary"):
            with st.spinner("Matching..."):
                dataset_id = dataset_options.get(selected_dataset) if selected_dataset != "None" else None
                match_result = client.post("/voice/match", json={
                    "text": text,
                    "dataset_id": dataset_id,
                    "confidence_threshold": 0.7,
                })

                if match_result:
                    st.session_state["matches"] = match_result
                    st.success(f"Found {len(match_result.get('parsed_items', []))} items")

    # Show matches
    if "matches" in st.session_state:
        st.subheader("Matched Items")
        matches = st.session_state["matches"]

        for i, item in enumerate(matches.get("parsed_items", [])):
            with st.expander(f"{item.get('item_text', 'Unknown')} - {item.get('quantity', 1)} {item.get('unit', 'units')}"):
                if item.get("best_match"):
                    match = item["best_match"]
                    st.write(f"**Matched to:** {match['item_name']}")
                    st.write(f"**Confidence:** {match['confidence']:.0%}")
                    st.write(f"**Category:** {match.get('category', 'N/A')}")
                else:
                    st.warning("No match found - needs manual entry")

                if item.get("alternatives"):
                    st.write("**Alternatives:**")
                    for alt in item["alternatives"]:
                        st.write(f"  - {alt['item_name']} ({alt['confidence']:.0%})")

        # Add to session button
        if st.session_state.get("current_session"):
            if st.button("Add All to Session"):
                session_id = st.session_state["current_session"]["session_id"]
                for item in matches.get("parsed_items", []):
                    client.post(f"/voice/sessions/{session_id}/records", params={
                        "raw_text": item.get("raw_text", ""),
                        "quantity": item.get("quantity", 1),
                        "item_name": item.get("best_match", {}).get("item_name") or item.get("item_text"),
                        "item_id": item.get("best_match", {}).get("item_id"),
                        "match_confidence": item.get("best_match", {}).get("confidence", 0),
                    })
                st.success("Added all items to session!")


def render_sessions_tab(client: APIClient):
    """Sessions list tab."""
    st.subheader("Voice Counting Sessions")

    sessions = client.get("/voice/sessions") or []

    if not sessions:
        st.info("No sessions yet. Create one in the Record/Upload tab.")
        return

    for session in sessions:
        with st.expander(f"{session['name']} - {session['status']}", expanded=session['status'] == 'in_progress'):
            st.write(f"**ID:** {session['session_id']}")
            st.write(f"**Created:** {session['created_at']}")
            st.write(f"**Items:** {session['items_counted']}")
            st.write(f"**Total Units:** {session['total_units']}")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("View Records", key=f"view_{session['session_id']}"):
                    records = client.get(f"/voice/sessions/{session['session_id']}/records")
                    st.session_state[f"records_{session['session_id']}"] = records

            with col2:
                if session['status'] == 'in_progress':
                    if st.button("Complete", key=f"complete_{session['session_id']}"):
                        client.post(f"/voice/sessions/{session['session_id']}/complete")
                        st.rerun()

            # Show records if loaded
            records_key = f"records_{session['session_id']}"
            if records_key in st.session_state:
                st.write("**Records:**")
                for rec in st.session_state[records_key]:
                    st.write(f"  - {rec['item_name'] or rec['raw_text']}: {rec['quantity']} {rec['unit']}")


def render_export_tab(client: APIClient):
    """Export tab."""
    st.subheader("Export Session")

    sessions = client.get("/voice/sessions") or []
    completed = [s for s in sessions if s.get("status") == "completed"]

    if not completed:
        st.info("Complete a session first to export.")
        return

    session_options = {s["name"]: s["session_id"] for s in completed}
    selected = st.selectbox("Select Session", options=list(session_options.keys()))

    if selected:
        session_id = session_options[selected]

        col1, col2 = st.columns(2)
        with col1:
            format_type = st.selectbox("Format", ["csv", "summary"])
        with col2:
            group_by = st.checkbox("Group by category")

        if st.button("Generate Export", type="primary"):
            export = client.get(f"/voice/sessions/{session_id}/export", params={
                "format": format_type,
                "group_by_category": group_by,
            })

            if export:
                st.session_state["export"] = export

        if "export" in st.session_state:
            export = st.session_state["export"]

            st.subheader("Export Result")

            # CSV for copy/paste
            st.write("**CSV (copy/paste to spreadsheet):**")
            st.code(export.get("csv_text", ""), language=None)

            # Summary
            st.write("**Summary:**")
            st.text(export.get("summary_text", ""))

            # Copy buttons
            st.download_button(
                "Download CSV",
                export.get("csv_text", ""),
                file_name="inventory_count.csv",
                mime="text/csv",
            )
