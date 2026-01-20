"""Items page - list and filter items."""

import streamlit as st
import pandas as pd

from ui.api_client import APIClient, APIError


def render_items_page(client: APIClient, dataset_id: str):
    """Render the items list page."""
    st.header("Items")

    # Filters
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        search = st.text_input(
            "Search",
            placeholder="Search items...",
            label_visibility="collapsed",
        )

    with col2:
        # Get categories for filter
        try:
            dataset = client.get_dataset(dataset_id)
            categories = ["All"] + dataset.get("categories", [])
        except Exception:
            categories = ["All"]

        category_filter = st.selectbox(
            "Category",
            categories,
            label_visibility="collapsed",
        )

    with col3:
        sort_by = st.selectbox(
            "Sort by",
            ["Name", "On Hand", "Usage", "Weeks OH"],
            label_visibility="collapsed",
        )

    # Fetch items
    try:
        items = client.get_items(
            dataset_id,
            search=search if search else None,
            category=category_filter if category_filter != "All" else None,
        )
    except APIError as e:
        st.error(f"Error loading items: {e}")
        return

    if not items:
        st.info("No items found.")
        return

    # Convert to DataFrame
    rows = []
    for item in items:
        stats = item.get("stats", {})
        rows.append({
            "item_id": item["item_id"],
            "Name": item["name"],
            "Category": item.get("category") or "-",
            "On Hand": stats.get("current_on_hand", 0),
            "Avg Usage": stats.get("avg_usage", 0),
            "Weeks OH": stats.get("weeks_on_hand") or 0,
            "Trend": stats.get("trend_direction", "stable"),
            "Records": stats.get("record_count", 0),
        })

    df = pd.DataFrame(rows)

    # Sort
    sort_col = {
        "Name": "Name",
        "On Hand": "On Hand",
        "Usage": "Avg Usage",
        "Weeks OH": "Weeks OH",
    }.get(sort_by, "Name")

    ascending = sort_by == "Name"
    df = df.sort_values(sort_col, ascending=ascending)

    # Display count
    st.caption(f"{len(df)} items")

    # Render as clickable table
    for _, row in df.iterrows():
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])

            with col1:
                if st.button(
                    f"**{row['Name']}**",
                    key=f"item_{row['item_id']}",
                    use_container_width=True,
                ):
                    st.session_state.view_item_id = row["item_id"]
                    st.rerun()

            with col2:
                st.caption(row["Category"])

            with col3:
                st.metric("On Hand", f"{row['On Hand']:.0f}", label_visibility="collapsed")

            with col4:
                st.metric("Avg Usage", f"{row['Avg Usage']:.1f}", label_visibility="collapsed")

            with col5:
                trend = row["Trend"]
                trend_icon = {"up": "📈", "down": "📉", "stable": "➡️"}.get(trend, "")
                woh = row["Weeks OH"]
                color = "red" if woh < 1 else "orange" if woh < 2 else "green"
                st.markdown(f":{color}[{woh:.1f} wk] {trend_icon}")
