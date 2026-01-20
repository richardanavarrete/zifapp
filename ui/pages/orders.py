"""Order Recommendations Page."""

import streamlit as st
import pandas as pd

from ui.api_client import get_client


def render():
    """Render the order recommendations page."""
    st.title("Order Recommendations")

    # Tabs
    tab1, tab2, tab3 = st.tabs(["Generate", "History", "Settings"])

    with tab1:
        render_generate_section()

    with tab2:
        render_history_section()

    with tab3:
        render_settings_section()


def render_generate_section():
    """Render the recommendation generation section."""
    st.subheader("Generate Order Recommendations")

    client = get_client()

    # Get datasets
    datasets_result = client.list_datasets()
    if not datasets_result.success or not datasets_result.data:
        st.info("No datasets available. Upload an inventory file first.")
        return

    datasets = datasets_result.data if isinstance(datasets_result.data, list) else []

    # Dataset selection
    selected_dataset = st.selectbox(
        "Select Dataset",
        options=[d.get('dataset_id', '') for d in datasets],
        format_func=lambda x: next(
            (d.get('name', x) for d in datasets if d.get('dataset_id') == x),
            x
        )
    )

    # Optional constraints
    with st.expander("Constraints (Optional)"):
        col1, col2 = st.columns(2)

        with col1:
            max_spend = st.number_input(
                "Max Total Spend ($)",
                min_value=0,
                value=0,
                help="Set to 0 for no limit"
            )

        with col2:
            max_cases = st.number_input(
                "Max Total Cases",
                min_value=0,
                value=0,
                help="Set to 0 for no limit"
            )

    # Generate button
    if st.button("Generate Recommendations", type="primary", disabled=not selected_dataset):
        constraints = {}
        if max_spend > 0:
            constraints["max_total_spend"] = max_spend
        if max_cases > 0:
            constraints["max_total_cases"] = max_cases

        with st.spinner("Generating recommendations..."):
            result = client.get_recommendations(
                dataset_id=selected_dataset,
                constraints=constraints if constraints else None,
            )

            if result.success:
                st.session_state['current_run'] = result.data
                st.success("Recommendations generated!")
            else:
                st.error(f"Failed to generate recommendations: {result.error}")

    # Display current run
    if 'current_run' in st.session_state and st.session_state['current_run']:
        display_run(st.session_state['current_run'])


def display_run(run_data: dict):
    """Display a run's recommendations."""
    st.divider()
    st.subheader("Results")

    # Summary metrics
    summary = run_data.get('summary', {})
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Items", summary.get('total_items', 0))
    with col2:
        st.metric("Total Spend", f"${summary.get('total_spend', 0):,.2f}")
    with col3:
        st.metric("With Warnings", summary.get('items_with_warnings', 0))
    with col4:
        st.metric("Run ID", run_data.get('run_id', 'N/A')[:12])

    # Vendor breakdown
    by_vendor = summary.get('by_vendor', {})
    if by_vendor:
        st.subheader("By Vendor")
        vendor_df = pd.DataFrame([
            {
                "Vendor": v,
                "Items": data.get('items_count', 0),
                "Spend": f"${data.get('total_spend', 0):,.2f}"
            }
            for v, data in by_vendor.items()
        ])
        st.dataframe(vendor_df, use_container_width=True, hide_index=True)

    # Recommendations table
    recommendations = run_data.get('recommendations', [])
    if recommendations:
        st.subheader("Recommendations")

        # Filter to items with suggested orders
        recs_with_orders = [r for r in recommendations if r.get('suggested_order', 0) > 0]

        if recs_with_orders:
            df = pd.DataFrame(recs_with_orders)

            # Select and order columns
            columns = [
                'display_name', 'category', 'vendor',
                'current_on_hand', 'weeks_on_hand', 'avg_weekly_usage',
                'suggested_order', 'total_cost',
                'reason_code', 'confidence'
            ]
            available_cols = [c for c in columns if c in df.columns]
            df = df[available_cols]

            # Format
            if 'total_cost' in df.columns:
                df['total_cost'] = df['total_cost'].apply(lambda x: f"${x:,.2f}")
            if 'weeks_on_hand' in df.columns:
                df['weeks_on_hand'] = df['weeks_on_hand'].apply(lambda x: f"{x:.1f}")

            st.dataframe(df, use_container_width=True, hide_index=True)

            # Approval actions
            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Approve All"):
                    client = get_client()
                    result = client.approve_run(run_data.get('run_id'))
                    if result.success:
                        st.success("Recommendations approved!")
                    else:
                        st.error(f"Approval failed: {result.error}")

        # Show warnings
        warnings = run_data.get('warnings', [])
        if warnings:
            with st.expander(f"Warnings ({len(warnings)})"):
                for w in warnings:
                    st.warning(f"{w.get('item_id', 'Unknown')}: {w.get('message', 'No message')}")


def render_history_section():
    """Render past runs history."""
    st.subheader("Run History")

    client = get_client()
    result = client.list_runs()

    if not result.success:
        st.error(f"Failed to load history: {result.error}")
        return

    runs = result.data if isinstance(result.data, list) else []

    if not runs:
        st.info("No past runs found.")
        return

    df = pd.DataFrame(runs)
    if 'created_at' in df.columns:
        df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M')

    st.dataframe(df, use_container_width=True, hide_index=True)

    # Load specific run
    selected_run = st.selectbox(
        "View run details",
        options=[r.get('run_id', '') for r in runs]
    )

    if selected_run and st.button("Load Run"):
        result = client.get_run(selected_run)
        if result.success:
            st.session_state['current_run'] = result.data
            st.rerun()
        else:
            st.error(f"Failed to load run: {result.error}")


def render_settings_section():
    """Render order settings."""
    st.subheader("Order Targets")

    client = get_client()
    result = client.get_targets()

    if not result.success:
        st.error(f"Failed to load targets: {result.error}")
        return

    targets = result.data if result.data else {}
    weeks_by_category = targets.get('weeks_by_category', {})

    st.write("Target weeks of inventory by category:")

    # Edit targets
    edited_targets = {}
    cols = st.columns(3)

    categories = list(weeks_by_category.keys())
    for i, category in enumerate(categories):
        with cols[i % 3]:
            edited_targets[category] = st.number_input(
                category,
                min_value=0.0,
                max_value=12.0,
                value=float(weeks_by_category.get(category, 4.0)),
                step=0.5,
                key=f"target_{category}"
            )

    if st.button("Save Targets"):
        new_targets = {
            "weeks_by_category": edited_targets,
            "item_overrides": targets.get('item_overrides', {}),
            "never_order": targets.get('never_order', []),
        }
        result = client.update_targets(new_targets)
        if result.success:
            st.success("Targets saved!")
        else:
            st.error(f"Failed to save: {result.error}")
