"""Upload page - file upload and dataset management."""

import streamlit as st

from ui.api_client import APIClient, APIError


def render_upload_page(client: APIClient):
    """Render the upload page."""
    st.header("Upload Inventory")

    st.write("""
    Upload your inventory spreadsheet (Excel or CSV). The system will
    automatically detect columns for:
    - **Item name** (required)
    - **On-hand quantity** (required)
    - **Usage** (optional)
    - **Category** (optional)
    - **Date** (optional)
    """)

    # File uploader
    uploaded_file = st.file_uploader(
        "Choose a file",
        type=["xlsx", "xls", "csv"],
        help="Upload Excel (.xlsx, .xls) or CSV files",
    )

    col1, col2 = st.columns(2)

    with col1:
        dataset_name = st.text_input(
            "Dataset Name",
            placeholder="My Inventory",
            help="Optional name for this dataset",
        )

    with col2:
        skip_rows = st.number_input(
            "Skip Rows",
            min_value=0,
            max_value=20,
            value=0,
            help="Number of header rows to skip",
        )

    if uploaded_file is not None:
        st.divider()

        # Preview
        st.subheader("Preview")
        st.caption(f"File: {uploaded_file.name} ({uploaded_file.size:,} bytes)")

        # Upload button
        if st.button("Upload & Process", type="primary"):
            with st.spinner("Processing..."):
                try:
                    result = client.upload_file_bytes(
                        file_bytes=uploaded_file.getvalue(),
                        filename=uploaded_file.name,
                        name=dataset_name or None,
                        skip_rows=skip_rows,
                    )

                    st.success("Upload successful!")

                    # Show results
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Items", result.get("items_count", 0))
                    with col2:
                        st.metric("Records", result.get("records_count", 0))
                    with col3:
                        st.metric("Periods", result.get("periods_count", 0))

                    # Warnings
                    warnings = result.get("warnings", [])
                    if warnings:
                        st.warning("Warnings:")
                        for w in warnings:
                            st.caption(f"- {w}")

                    # Categories found
                    categories = result.get("categories_found", [])
                    if categories:
                        st.info(f"Categories found: {', '.join(categories)}")

                    # Set as selected dataset
                    st.session_state.selected_dataset_id = result.get("dataset_id")

                    st.balloons()

                except APIError as e:
                    st.error(f"Upload failed: {e}")
                except Exception as e:
                    st.error(f"Error: {e}")

    st.divider()

    # Existing datasets
    st.subheader("Existing Datasets")

    try:
        datasets = client.list_datasets()
    except Exception:
        datasets = []

    if not datasets:
        st.info("No datasets uploaded yet.")
    else:
        for ds in datasets:
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

                with col1:
                    st.write(f"**{ds['name']}**")
                    st.caption(f"ID: {ds['dataset_id']}")

                with col2:
                    st.metric("Items", ds.get("items_count", 0), label_visibility="collapsed")

                with col3:
                    st.metric("Records", ds.get("records_count", 0), label_visibility="collapsed")

                with col4:
                    if st.button("Delete", key=f"del_{ds['dataset_id']}"):
                        try:
                            client.delete_dataset(ds["dataset_id"])
                            st.rerun()
                        except APIError as e:
                            st.error(f"Delete failed: {e}")

                st.divider()
