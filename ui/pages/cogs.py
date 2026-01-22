"""COGS Analysis Page."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from ui.api_client import get_client


def render():
    """Render the COGS analysis page."""
    st.title("COGS Analysis")

    # Tabs
    tab1, tab2, tab3 = st.tabs(["Pour Cost", "Variance", "Reports"])

    with tab1:
        render_pour_cost_section()

    with tab2:
        render_variance_section()

    with tab3:
        render_reports_section()


def render_pour_cost_section():
    """Render pour cost analysis section."""
    st.subheader("Pour Cost Analysis")

    client = get_client()

    # Get datasets
    datasets_result = client.list_datasets()
    if not datasets_result.success or not datasets_result.data:
        st.info("No datasets available. Upload an inventory file first.")
        return

    datasets = datasets_result.data if isinstance(datasets_result.data, list) else []

    # Inputs
    col1, col2 = st.columns(2)

    with col1:
        selected_dataset = st.selectbox(
            "Dataset",
            options=[d.get('dataset_id', '') for d in datasets],
            format_func=lambda x: next(
                (d.get('name', x) for d in datasets if d.get('dataset_id') == x),
                x
            ),
            key="pour_cost_dataset"
        )

    with col2:
        category_filter = st.selectbox(
            "Category",
            options=["All", "Whiskey", "Vodka", "Gin", "Tequila", "Rum", "Wine"],
            index=0,
            key="pour_cost_category"
        )

    if st.button("Calculate Pour Costs", type="primary"):
        with st.spinner("Calculating..."):
            result = client.calculate_pour_costs(
                dataset_id=selected_dataset,
                category=category_filter if category_filter != "All" else None,
            )

            if result.success:
                st.session_state['pour_costs'] = result.data
            else:
                st.error(f"Calculation failed: {result.error}")

    # Display results
    if 'pour_costs' in st.session_state and st.session_state['pour_costs']:
        pour_costs = st.session_state['pour_costs']
        if isinstance(pour_costs, list) and pour_costs:
            df = pd.DataFrame(pour_costs)
            st.dataframe(df, use_container_width=True, hide_index=True)


def render_variance_section():
    """Render variance analysis section."""
    st.subheader("Variance Analysis")
    st.caption("Compare theoretical usage (from sales) to actual inventory usage")

    client = get_client()

    # Get datasets
    datasets_result = client.list_datasets()
    if not datasets_result.success or not datasets_result.data:
        st.info("No datasets available. Upload an inventory file first.")
        return

    datasets = datasets_result.data if isinstance(datasets_result.data, list) else []

    # Dataset selection
    selected_dataset = st.selectbox(
        "Dataset",
        options=[d.get('dataset_id', '') for d in datasets],
        format_func=lambda x: next(
            (d.get('name', x) for d in datasets if d.get('dataset_id') == x),
            x
        ),
        key="variance_dataset"
    )

    # Date range
    col1, col2 = st.columns(2)
    with col1:
        period_start = st.date_input(
            "Period Start",
            value=date.today() - timedelta(days=30),
            key="variance_start"
        )
    with col2:
        period_end = st.date_input(
            "Period End",
            value=date.today(),
            key="variance_end"
        )

    # Sales mix upload
    st.divider()
    st.write("Upload sales mix for comparison:")

    uploaded_file = st.file_uploader(
        "Sales Mix CSV",
        type=["csv"],
        help="Upload your GEMpos sales mix export"
    )

    if uploaded_file:
        if st.button("Upload Sales Mix"):
            with st.spinner("Uploading..."):
                result = client.upload_sales_mix(
                    file_content=uploaded_file,
                    filename=uploaded_file.name,
                )
                if result.success:
                    st.session_state['sales_mix_file_id'] = result.data.get('file_id')
                    st.success("Sales mix uploaded!")
                else:
                    st.error(f"Upload failed: {result.error}")

    # Run analysis
    if st.button("Run Variance Analysis", type="primary"):
        with st.spinner("Analyzing..."):
            result = client.analyze_variance(
                dataset_id=selected_dataset,
                period_start=period_start.isoformat(),
                period_end=period_end.isoformat(),
                sales_mix_file_id=st.session_state.get('sales_mix_file_id'),
            )

            if result.success:
                st.session_state['variance_result'] = result.data
            else:
                st.error(f"Analysis failed: {result.error}")

    # Display results
    if 'variance_result' in st.session_state and st.session_state['variance_result']:
        result = st.session_state['variance_result']

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Theoretical Cost", f"${result.get('total_theoretical_cost', 0):,.2f}")
        with col2:
            st.metric("Actual Cost", f"${result.get('total_actual_cost', 0):,.2f}")
        with col3:
            st.metric("Variance", f"${result.get('total_variance_cost', 0):,.2f}")
        with col4:
            st.metric("Variance %", f"{result.get('overall_variance_percent', 0):.1f}%")

        # Items table
        items = result.get('items', [])
        if items:
            st.subheader("Item Details")
            df = pd.DataFrame(items)
            st.dataframe(df, use_container_width=True, hide_index=True)


def render_reports_section():
    """Render historical reports section."""
    st.subheader("Historical Reports")

    # Placeholder - would load from API
    st.info("No historical reports yet. Run an analysis to generate reports.")
