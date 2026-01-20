"""Item detail page - drill-down view with charts."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui.api_client import APIClient, APIError


def render_item_detail(client: APIClient, dataset_id: str, item_id: str):
    """Render detailed view for a single item."""

    # Back button
    if st.button("← Back to Items"):
        st.session_state.view_item_id = None
        st.rerun()

    # Fetch detail
    try:
        data = client.get_item_detail(dataset_id, item_id)
    except APIError as e:
        st.error(f"Error loading item: {e}")
        return

    item = data.get("item", {})
    stats = data.get("stats", {})
    history = data.get("history", [])

    # Header
    st.header(item.get("name", "Unknown"))

    if item.get("category"):
        st.caption(f"Category: {item['category']}")

    st.divider()

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Current On Hand", f"{stats.get('current_on_hand', 0):.0f}")

    with col2:
        avg_usage = stats.get("avg_usage", 0)
        recent_usage = stats.get("avg_usage_recent", 0)
        delta = recent_usage - avg_usage if avg_usage else 0
        st.metric(
            "Avg Usage",
            f"{avg_usage:.1f}",
            delta=f"{delta:+.1f}" if delta else None,
        )

    with col3:
        woh = stats.get("weeks_on_hand")
        st.metric("Weeks on Hand", f"{woh:.1f}" if woh else "N/A")

    with col4:
        trend = stats.get("trend_direction", "stable")
        trend_pct = stats.get("trend_percent_change", 0)
        trend_icon = {"up": "📈", "down": "📉", "stable": "➡️"}.get(trend, "")
        st.metric("Trend", f"{trend_icon} {trend_pct:+.1f}%")

    st.divider()

    # Charts
    if history:
        st.subheader("Usage History")

        # Prepare data
        hist_df = pd.DataFrame(history)
        hist_df["date"] = pd.to_datetime(hist_df["date"])

        # Usage chart
        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=hist_df["date"],
            y=hist_df["usage"],
            name="Usage",
            marker_color="steelblue",
        ))

        # Add rolling average if available
        rolling_avg = data.get("rolling_avg_4wk", [])
        if rolling_avg and len(rolling_avg) == len(hist_df):
            fig.add_trace(go.Scatter(
                x=hist_df["date"],
                y=rolling_avg,
                name="4-Week Avg",
                line=dict(color="orange", width=2),
            ))

        fig.update_layout(
            title="Usage Over Time",
            xaxis_title="Date",
            yaxis_title="Usage",
            hovermode="x unified",
        )

        st.plotly_chart(fig, use_container_width=True)

        # On-hand chart
        fig2 = go.Figure()

        fig2.add_trace(go.Scatter(
            x=hist_df["date"],
            y=hist_df["on_hand"],
            name="On Hand",
            fill="tozeroy",
            line=dict(color="green"),
        ))

        fig2.update_layout(
            title="Inventory Levels",
            xaxis_title="Date",
            yaxis_title="On Hand",
            hovermode="x unified",
        )

        st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # Statistics detail
    st.subheader("Statistics")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Usage Statistics**")
        st.write(f"- Total Usage: {stats.get('total_usage', 0):.1f}")
        st.write(f"- Min Usage: {stats.get('min_usage', 0):.1f}")
        st.write(f"- Max Usage: {stats.get('max_usage', 0):.1f}")
        st.write(f"- Std Deviation: {stats.get('std_deviation', 0):.2f}")
        st.write(f"- Coefficient of Variation: {stats.get('coefficient_of_variation', 0):.2f}")

    with col2:
        st.write("**Data Quality**")
        st.write(f"- Records: {stats.get('record_count', 0)}")
        st.write(f"- Last Count: {stats.get('last_count_date', 'N/A')}")

        if stats.get("has_negative_usage"):
            st.warning("Has negative usage values")
        if stats.get("has_gaps"):
            st.warning("Has data gaps (>2 weeks)")

    # Raw history table
    if history:
        with st.expander("View Raw Data"):
            st.dataframe(
                hist_df,
                column_config={
                    "date": st.column_config.DateColumn("Date"),
                    "usage": st.column_config.NumberColumn("Usage", format="%.1f"),
                    "on_hand": st.column_config.NumberColumn("On Hand", format="%.1f"),
                },
                hide_index=True,
                use_container_width=True,
            )
