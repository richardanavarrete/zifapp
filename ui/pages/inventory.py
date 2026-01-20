"""Inventory Management Page."""

import streamlit as st
import pandas as pd
from datetime import datetime

from ui.api_client import get_client


def render():
    """Render the inventory management page."""
    st.title("Inventory Management")

    # Tabs for different views
    tab1, tab2, tab3 = st.tabs(["Upload", "Datasets", "Items"])

    with tab1:
        render_upload_section()

    with tab2:
        render_datasets_section()

    with tab3:
        render_items_section()


def render_upload_section():
    """Render the file upload section."""
    st.subheader("Upload Inventory File")

    uploaded_file = st.file_uploader(
        "Choose an Excel file",
        type=["xlsx", "xls"],
        help="Upload your weekly inventory export"
    )

    dataset_name = st.text_input(
        "Dataset Name (optional)",
        placeholder="e.g., March 2024 Inventory"
    )

    if uploaded_file is not None:
        st.info(f"Selected: {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")

        if st.button("Upload", type="primary"):
            with st.spinner("Uploading and processing..."):
                client = get_client()
                result = client.upload_inventory(
                    file_content=uploaded_file,
                    filename=uploaded_file.name,
                    name=dataset_name or None,
                )

                if result.success:
                    st.success("File uploaded successfully!")
                    st.json(result.data)
                else:
                    st.error(f"Upload failed: {result.error}")


def render_datasets_section():
    """Render the datasets list section."""
    st.subheader("Uploaded Datasets")

    client = get_client()
    result = client.list_datasets()

    if not result.success:
        st.error(f"Failed to load datasets: {result.error}")
        return

    datasets = result.data if isinstance(result.data, list) else []

    if not datasets:
        st.info("No datasets uploaded yet. Upload an inventory file to get started.")
        return

    # Display as table
    df = pd.DataFrame(datasets)
    if not df.empty:
        # Format columns
        if 'created_at' in df.columns:
            df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M')

        st.dataframe(
            df[['dataset_id', 'name', 'items_count', 'weeks_count', 'created_at']],
            use_container_width=True,
            hide_index=True,
        )

    # Dataset actions
    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        selected_id = st.selectbox(
            "Select dataset",
            options=[d.get('dataset_id', '') for d in datasets],
            format_func=lambda x: next(
                (d.get('name', x) for d in datasets if d.get('dataset_id') == x),
                x
            )
        )

    with col2:
        if st.button("Analyze Features"):
            if selected_id:
                with st.spinner("Running analysis..."):
                    result = client.analyze_dataset(selected_id)
                    if result.success:
                        st.success("Analysis complete!")
                        st.session_state['features'] = result.data
                    else:
                        st.error(f"Analysis failed: {result.error}")

    # Show features if available
    if 'features' in st.session_state and st.session_state['features']:
        st.subheader("Item Features")
        features_df = pd.DataFrame(st.session_state['features'])
        st.dataframe(features_df, use_container_width=True, hide_index=True)


def render_items_section():
    """Render the items view section."""
    st.subheader("Inventory Items")

    client = get_client()

    # Get datasets for selection
    datasets_result = client.list_datasets()
    if not datasets_result.success or not datasets_result.data:
        st.info("No datasets available. Upload an inventory file first.")
        return

    datasets = datasets_result.data if isinstance(datasets_result.data, list) else []

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        selected_dataset = st.selectbox(
            "Dataset",
            options=[d.get('dataset_id', '') for d in datasets],
            format_func=lambda x: next(
                (d.get('name', x) for d in datasets if d.get('dataset_id') == x),
                x
            )
        )

    with col2:
        category_filter = st.selectbox(
            "Category",
            options=["All", "Whiskey", "Vodka", "Gin", "Tequila", "Rum", "Wine", "Draft Beer", "Bottled Beer"],
            index=0,
        )

    with col3:
        search = st.text_input("Search", placeholder="Item name...")

    if selected_dataset:
        result = client.list_items(
            dataset_id=selected_dataset,
            category=category_filter if category_filter != "All" else None,
            search=search if search else None,
        )

        if result.success:
            items = result.data if isinstance(result.data, list) else []
            if items:
                df = pd.DataFrame(items)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No items found matching your criteria.")
        else:
            st.error(f"Failed to load items: {result.error}")
