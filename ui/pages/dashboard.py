"""Dashboard page - overview and key metrics."""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from ui.api_client import APIClient, APIError


def render_dashboard(client: APIClient, dataset_id: str):
    """Render the dashboard page."""
    st.header("Dashboard")

    try:
        data = client.get_dashboard(dataset_id)
    except APIError as e:
        st.error(f"Error loading dashboard: {e}")
        return

    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Items", data["total_items"])

    with col2:
        st.metric("Total On Hand", f"{data['total_on_hand']:,.0f}")

    with col3:
        st.metric("Periods", data["periods_count"])

    with col4:
        date_range = data.get("date_range", {})
        if date_range.get("start") and date_range.get("end"):
            st.metric("Date Range", f"{date_range['start']} to {date_range['end']}")
        else:
            st.metric("Date Range", "N/A")

    st.divider()

    # Alerts section
    alerts = data.get("alerts", {})
    if any([
        alerts.get("low_stock_count", 0) > 0,
        alerts.get("data_issues_count", 0) > 0,
    ]):
        st.subheader("Alerts")

        alert_col1, alert_col2, alert_col3 = st.columns(3)

        with alert_col1:
            low_stock = alerts.get("low_stock_count", 0)
            if low_stock > 0:
                st.warning(f"**{low_stock}** items with low stock (<1 week)")
                if alerts.get("low_stock_items"):
                    for item in alerts["low_stock_items"][:5]:
                        st.caption(f"- {item}")

        with alert_col2:
            trending_up = alerts.get("trending_up_count", 0)
            trending_down = alerts.get("trending_down_count", 0)
            if trending_up > 0:
                st.info(f"**{trending_up}** items trending up")
            if trending_down > 0:
                st.info(f"**{trending_down}** items trending down")

        with alert_col3:
            data_issues = alerts.get("data_issues_count", 0)
            if data_issues > 0:
                st.error(f"**{data_issues}** items with data quality issues")

        st.divider()

    # Category breakdown
    categories = data.get("categories", {})
    if categories:
        st.subheader("By Category")

        # Prepare data for charts
        cat_data = []
        for cat_name, cat_info in categories.items():
            cat_data.append({
                "Category": cat_name,
                "Items": cat_info.get("items_count", 0),
                "On Hand": cat_info.get("total_on_hand", 0),
                "Avg Weeks OH": cat_info.get("avg_weeks_on_hand") or 0,
            })

        cat_df = pd.DataFrame(cat_data)

        col1, col2 = st.columns(2)

        with col1:
            # Items by category
            fig = px.pie(
                cat_df,
                values="Items",
                names="Category",
                title="Items by Category",
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # On-hand by category
            fig = px.bar(
                cat_df.sort_values("On Hand", ascending=True),
                x="On Hand",
                y="Category",
                orientation="h",
                title="On Hand by Category",
            )
            st.plotly_chart(fig, use_container_width=True)

        # Category table
        st.dataframe(
            cat_df,
            column_config={
                "Category": st.column_config.TextColumn("Category"),
                "Items": st.column_config.NumberColumn("Items", format="%d"),
                "On Hand": st.column_config.NumberColumn("On Hand", format="%.1f"),
                "Avg Weeks OH": st.column_config.NumberColumn("Avg Weeks", format="%.1f"),
            },
            hide_index=True,
            use_container_width=True,
        )
