"""
Order Recommendations Page

Agentic ordering - smart recommendations based on usage patterns.
"""

import streamlit as st

from ui.api_client import APIClient


def render_orders_page(client: APIClient):
    """Render the order recommendations page."""
    st.header("Order Recommendations")
    st.markdown("Generate smart order suggestions based on your usage patterns.")

    # Tabs
    tab_generate, tab_history, tab_export = st.tabs(["Generate", "History", "Export"])

    with tab_generate:
        render_generate_tab(client)

    with tab_history:
        render_history_tab(client)

    with tab_export:
        render_export_tab(client)


def render_generate_tab(client: APIClient):
    """Generate recommendations tab."""
    st.subheader("Generate Recommendations")

    # Dataset selection
    datasets = client.get("/inventory/datasets") or []

    if not datasets:
        st.warning("Upload inventory data first to generate recommendations.")
        return

    dataset_options = {d["name"]: d["dataset_id"] for d in datasets}
    selected_dataset = st.selectbox("Select Dataset", options=list(dataset_options.keys()))

    st.divider()

    # Configuration
    st.subheader("Targets")
    col1, col2 = st.columns(2)

    with col1:
        default_weeks = st.number_input(
            "Default target weeks",
            min_value=0.5,
            max_value=12.0,
            value=2.0,
            step=0.5,
            help="How many weeks of inventory to maintain"
        )

    with col2:
        low_stock_weeks = st.number_input(
            "Low stock threshold",
            min_value=0.1,
            max_value=4.0,
            value=1.0,
            step=0.1,
            help="Alert when below this many weeks"
        )

    # Category-specific targets
    with st.expander("Category-specific targets (optional)"):
        st.markdown("Set different targets for specific categories:")
        cat_targets = {}

        # Get categories from dataset
        if selected_dataset:
            ds = client.get(f"/inventory/datasets/{dataset_options[selected_dataset]}")
            if ds and ds.get("categories"):
                for cat in ds["categories"][:10]:  # Limit to 10
                    val = st.number_input(
                        cat,
                        min_value=0.5,
                        max_value=12.0,
                        value=default_weeks,
                        step=0.5,
                        key=f"cat_{cat}"
                    )
                    if val != default_weeks:
                        cat_targets[cat] = val

    # Constraints
    st.subheader("Constraints")
    col1, col2 = st.columns(2)

    with col1:
        max_spend = st.number_input(
            "Max total spend ($)",
            min_value=0,
            value=0,
            step=100,
            help="0 = no limit"
        )

    with col2:
        max_items = st.number_input(
            "Max items",
            min_value=0,
            value=0,
            step=10,
            help="0 = no limit"
        )

    st.divider()

    # Generate button
    if st.button("Generate Recommendations", type="primary", use_container_width=True):
        with st.spinner("Analyzing usage patterns..."):
            request = {
                "dataset_id": dataset_options[selected_dataset],
                "targets": {
                    "default_weeks": default_weeks,
                    "by_category": cat_targets,
                },
                "constraints": {
                    "low_stock_weeks": low_stock_weeks,
                    "max_spend": max_spend if max_spend > 0 else None,
                    "max_items": max_items if max_items > 0 else None,
                },
            }

            result = client.post("/orders/recommend", json=request)

            if result:
                st.session_state["recommendations"] = result
                st.success(f"Generated {result.get('total_items', 0)} recommendations!")
            else:
                st.error("Failed to generate recommendations")

    # Show results
    if "recommendations" in st.session_state:
        render_recommendations(st.session_state["recommendations"])


def render_recommendations(run: dict):
    """Render recommendation results."""
    st.divider()
    st.subheader("Recommendations")

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Items", run.get("total_items", 0))
    with col2:
        st.metric("Total Spend", f"${run.get('total_spend', 0):.2f}")
    with col3:
        st.metric("Low Stock", run.get("low_stock_count", 0))
    with col4:
        st.metric("Data Issues", len(run.get("data_issues", [])))

    # Breakdown by reason
    if run.get("by_reason"):
        st.write("**By Reason:**")
        for reason, count in run["by_reason"].items():
            st.write(f"  - {reason}: {count}")

    st.divider()

    # Recommendations table
    recommendations = run.get("recommendations", [])

    if not recommendations:
        st.info("No recommendations at this time.")
        return

    # Group by vendor option
    group_by = st.radio("Group by", ["None", "Vendor", "Category"], horizontal=True)

    if group_by == "Vendor":
        for vendor, data in run.get("by_vendor", {}).items():
            with st.expander(f"{vendor} - {data['items']} items (${data['spend']:.2f})"):
                vendor_recs = [r for r in recommendations if r.get("vendor") == vendor]
                render_rec_table(vendor_recs)

    elif group_by == "Category":
        for category, data in run.get("by_category", {}).items():
            with st.expander(f"{category} - {data['items']} items (${data['spend']:.2f})"):
                cat_recs = [r for r in recommendations if r.get("category") == category]
                render_rec_table(cat_recs)
    else:
        render_rec_table(recommendations)


def render_rec_table(recommendations: list):
    """Render a table of recommendations."""
    for rec in recommendations:
        col1, col2, col3, col4 = st.columns([3, 1, 1, 2])

        with col1:
            st.write(f"**{rec['item_name']}**")
            if rec.get("warnings"):
                st.warning(rec["warnings"][0])

        with col2:
            st.write(f"On hand: {rec['on_hand']:.1f}")
            st.write(f"Avg use: {rec['avg_usage']:.1f}/wk")

        with col3:
            st.write(f"**Order: {rec['suggested_qty']}**")
            if rec.get("total_cost"):
                st.write(f"${rec['total_cost']:.2f}")

        with col4:
            confidence_color = {
                "high": "green",
                "medium": "orange",
                "low": "red"
            }.get(rec.get("confidence"), "gray")

            st.markdown(f":{confidence_color}[{rec.get('confidence', 'unknown')}]")
            st.caption(rec.get("reason_text", ""))

        st.divider()


def render_history_tab(client: APIClient):
    """History tab."""
    st.subheader("Recommendation History")

    runs = client.get("/orders/runs") or []

    if not runs:
        st.info("No recommendation runs yet.")
        return

    for run in runs[:10]:  # Show last 10
        with st.expander(f"{run['created_at'][:10]} - {run['total_items']} items (${run['total_spend']:.2f})"):
            st.write(f"**Run ID:** {run['run_id']}")
            st.write(f"**Dataset:** {run['dataset_id']}")
            st.write(f"**Status:** {run['status']}")

            if st.button("Load Details", key=f"load_{run['run_id']}"):
                full_run = client.get(f"/orders/runs/{run['run_id']}")
                if full_run:
                    st.session_state["recommendations"] = full_run
                    st.rerun()


def render_export_tab(client: APIClient):
    """Export tab."""
    st.subheader("Export Recommendations")

    if "recommendations" not in st.session_state:
        st.info("Generate recommendations first.")
        return

    run = st.session_state["recommendations"]
    run_id = run.get("run_id")

    col1, col2 = st.columns(2)
    with col1:
        group_by_vendor = st.checkbox("Group by vendor", value=True)

    if st.button("Generate Export", type="primary"):
        export = client.get(f"/orders/runs/{run_id}/export", params={
            "group_by_vendor": group_by_vendor,
        })

        if export:
            st.session_state["order_export"] = export

    if "order_export" in st.session_state:
        export = st.session_state["order_export"]

        st.subheader("Export Result")

        # CSV
        st.write("**CSV (copy/paste to spreadsheet):**")
        st.code(export.get("csv_text", ""), language=None)

        # Summary
        st.write("**Summary:**")
        st.text(export.get("summary_text", ""))

        # Download
        st.download_button(
            "Download CSV",
            export.get("csv_text", ""),
            file_name="order_recommendations.csv",
            mime="text/csv",
        )
