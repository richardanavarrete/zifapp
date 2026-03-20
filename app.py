"""
smallCOGS - Inventory Management & COGS Analysis
Streamlit application for uploading, analyzing, and managing inventory data.
"""

import os
import uuid
import tempfile

import streamlit as st
import pandas as pd

from smallcogs.services.inventory_service import InventoryService
from smallcogs.services.order_service import OrderService
from smallcogs.models.inventory import ItemFilter
from smallcogs.models.orders import RecommendRequest, OrderTargets, OrderConstraints, SalesForecast


# ---------------------------------------------------------------------------
# Session state & services
# ---------------------------------------------------------------------------

def get_inventory_service() -> InventoryService:
    if "inventory_service" not in st.session_state:
        st.session_state.inventory_service = InventoryService(storage_path="./data")
    return st.session_state.inventory_service


def get_order_service() -> OrderService:
    if "order_service" not in st.session_state:
        st.session_state.order_service = OrderService()
    return st.session_state.order_service


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="smallCOGS",
    page_icon="\U0001F4E6",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("smallCOGS")
    st.caption("Inventory Management & Analysis")
    st.divider()

    page = st.radio(
        "Navigation",
        ["Dashboard", "Inventory", "Upload", "Order Recommendations"],
        label_visibility="collapsed",
    )

    st.divider()

    # Dataset selector
    service = get_inventory_service()
    datasets = service.list_datasets()

    if datasets:
        dataset_names = {ds.dataset_id: ds.name for ds in datasets}
        current_id = st.session_state.get("active_dataset_id")
        if current_id not in dataset_names:
            current_id = datasets[0].dataset_id

        selected_id = st.selectbox(
            "Active Dataset",
            options=list(dataset_names.keys()),
            format_func=lambda x: dataset_names[x],
            index=list(dataset_names.keys()).index(current_id) if current_id in dataset_names else 0,
        )
        st.session_state.active_dataset_id = selected_id
    else:
        st.info("No datasets yet. Upload a file to get started.")
        st.session_state.active_dataset_id = None


# ===================================================================
# UPLOAD PAGE
# ===================================================================

def render_upload():
    st.header("Upload Inventory Data")
    st.write("Upload an Excel (.xlsx, .xls) or CSV file with your inventory data.")

    uploaded_file = st.file_uploader(
        "Choose a file",
        type=["xlsx", "xls", "csv"],
        help="Supported: Excel and CSV files with inventory counts",
    )

    col1, col2 = st.columns(2)
    with col1:
        dataset_name = st.text_input("Dataset Name (optional)", placeholder="e.g. March 2026 Inventory")
    with col2:
        skip_rows = st.number_input("Header rows to skip", min_value=0, value=0)

    if uploaded_file is not None:
        if st.button("Process File", type="primary"):
            with st.spinner("Parsing file..."):
                # Save to temp file
                suffix = "." + uploaded_file.name.rsplit(".", 1)[-1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded_file.read())
                    tmp_path = tmp.name

                try:
                    svc = get_inventory_service()
                    result = svc.upload_file(
                        file_path=tmp_path,
                        name=dataset_name or uploaded_file.name.rsplit(".", 1)[0],
                        skip_rows=skip_rows,
                    )

                    st.session_state.active_dataset_id = result.dataset_id

                    st.success(f"Uploaded **{result.filename}** successfully!")

                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Items", result.items_count)
                    m2.metric("Records", result.records_count)
                    m3.metric("Periods", result.periods_count)
                    m4.metric("Categories", len(result.categories_found))

                    if result.warnings:
                        with st.expander(f"Warnings ({len(result.warnings)})"):
                            for w in result.warnings:
                                st.warning(w)

                except ValueError as e:
                    st.error(str(e))
                finally:
                    os.unlink(tmp_path)


# ===================================================================
# DASHBOARD PAGE
# ===================================================================

def render_dashboard():
    st.header("Dashboard")

    dataset_id = st.session_state.get("active_dataset_id")
    if not dataset_id:
        st.info("Upload a dataset to see your dashboard.")
        return

    svc = get_inventory_service()
    stats = svc.get_dashboard_stats(dataset_id)
    if not stats:
        st.warning("Dataset not found.")
        return

    # --- KPI cards ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Items", f"{stats['total_items']:,}")
    c2.metric("Total On Hand", f"{stats['total_on_hand']:,.0f}")
    c3.metric("Periods", stats["periods_count"])

    dr = stats.get("date_range", {})
    date_label = ""
    if dr.get("start") and dr.get("end"):
        date_label = f"{dr['start']} to {dr['end']}"
    c4.metric("Date Range", date_label or "N/A")

    st.divider()

    # --- Alerts ---
    alerts = stats.get("alerts", {})
    low_count = alerts.get("low_stock_count", 0)
    up_count = alerts.get("trending_up_count", 0)
    down_count = alerts.get("trending_down_count", 0)
    issues_count = alerts.get("data_issues_count", 0)

    if low_count or up_count or down_count or issues_count:
        st.subheader("Alerts")
        ac1, ac2, ac3, ac4 = st.columns(4)
        if low_count:
            ac1.error(f"**{low_count}** Low Stock Items")
        if up_count:
            ac2.info(f"**{up_count}** Trending Up")
        if down_count:
            ac3.warning(f"**{down_count}** Trending Down")
        if issues_count:
            ac4.warning(f"**{issues_count}** Data Issues")

        low_items = alerts.get("low_stock_items", [])
        if low_items:
            with st.expander("Low Stock Items"):
                for name in low_items:
                    st.write(f"- {name}")

    # --- Category Breakdown ---
    categories = stats.get("categories", {})
    if categories:
        st.subheader("Category Breakdown")

        cat_rows = []
        for cat_name, cat_data in categories.items():
            cat_rows.append({
                "Category": cat_name,
                "Items": cat_data.get("items_count", 0),
                "Total On Hand": cat_data.get("total_on_hand", 0),
                "Avg Usage": round(cat_data.get("avg_usage", 0), 1),
            })

        if cat_rows:
            df = pd.DataFrame(cat_rows)
            st.dataframe(df, use_container_width=True, hide_index=True)


# ===================================================================
# INVENTORY PAGE
# ===================================================================

def render_inventory():
    st.header("Inventory")

    dataset_id = st.session_state.get("active_dataset_id")
    if not dataset_id:
        st.info("Upload a dataset to view inventory.")
        return

    svc = get_inventory_service()
    dataset = svc.get_dataset(dataset_id)
    if not dataset:
        st.warning("Dataset not found.")
        return

    # --- Filters ---
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        search = st.text_input("Search items", placeholder="Type to search...")
    with fc2:
        cats = ["All"] + sorted(dataset.categories)
        cat_filter = st.selectbox("Category", cats)
    with fc3:
        vendors = ["All"] + sorted(dataset.vendors)
        vendor_filter = st.selectbox("Vendor", vendors)

    filters = ItemFilter(
        search=search if search else None,
        categories=[cat_filter] if cat_filter != "All" else None,
        vendors=[vendor_filter] if vendor_filter != "All" else None,
    )

    items = svc.get_items(dataset_id, filters, include_stats=True)

    st.caption(f"{len(items)} items found")

    if not items:
        st.info("No items match your filters.")
        return

    # Build table
    rows = []
    for item in items:
        s = item.get("stats", {})
        weeks = s.get("weeks_on_hand")
        trend = s.get("trend_direction", "stable")

        if weeks is not None:
            if weeks < 1:
                status = "Critical"
            elif weeks < 2:
                status = "Low"
            elif weeks > 8:
                status = "Overstock"
            else:
                status = "Good"
        else:
            status = "-"

        trend_icon = {"up": "\u2191", "down": "\u2193", "stable": "\u2192"}.get(trend, "")

        rows.append({
            "Item": item["name"],
            "Category": item.get("category") or "-",
            "Vendor": item.get("vendor") or "-",
            "On Hand": s.get("current_on_hand", 0),
            "Avg Usage": round(s.get("avg_usage", 0), 1),
            "Weeks Left": round(weeks, 1) if weeks else "-",
            "Trend": trend_icon,
            "Status": status,
        })

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "On Hand": st.column_config.NumberColumn(format="%.0f"),
            "Avg Usage": st.column_config.NumberColumn(format="%.1f"),
        },
    )

    # --- Item Detail ---
    st.divider()
    st.subheader("Item Detail")
    item_names = {item["name"]: item["item_id"] for item in items}
    selected_name = st.selectbox("Select an item", list(item_names.keys()))

    if selected_name:
        detail = svc.get_item_detail(dataset_id, item_names[selected_name])
        if detail:
            d_item = detail.get("item", {})
            d_stats = detail.get("stats", {})
            history = detail.get("history", [])

            dc1, dc2, dc3, dc4 = st.columns(4)
            dc1.metric("On Hand", f"{d_stats.get('current_on_hand', 0):.0f}")
            dc2.metric("Avg Usage", f"{d_stats.get('avg_usage', 0):.1f}")
            woh = d_stats.get("weeks_on_hand")
            dc3.metric("Weeks on Hand", f"{woh:.1f}" if woh else "N/A")
            dc4.metric("Trend", d_stats.get("trend_direction", "stable"))

            if history:
                hist_df = pd.DataFrame(history)
                if "date" in hist_df.columns and "usage" in hist_df.columns:
                    hist_df["date"] = pd.to_datetime(hist_df["date"])
                    st.line_chart(hist_df.set_index("date")[["usage", "on_hand"]])


# ===================================================================
# ORDERS PAGE
# ===================================================================

def render_orders():
    st.header("Order Recommendations")

    dataset_id = st.session_state.get("active_dataset_id")
    if not dataset_id:
        st.info("Upload a dataset to generate order recommendations.")
        return

    svc = get_inventory_service()
    dataset = svc.get_dataset(dataset_id)
    if not dataset:
        st.warning("Dataset not found.")
        return

    order_svc = get_order_service()

    # --- Configuration ---
    with st.expander("Order Settings", expanded=False):
        sc1, sc2 = st.columns(2)
        with sc1:
            target_weeks = st.number_input("Target weeks of stock", min_value=0.5, value=2.0, step=0.5)
            low_stock_weeks = st.number_input("Low stock threshold (weeks)", min_value=0.0, value=1.0, step=0.5)
        with sc2:
            max_spend = st.number_input("Max budget ($)", min_value=0.0, value=0.0, step=100.0, help="0 = no limit")
            overstock_weeks = st.number_input("Overstock threshold (weeks)", min_value=1.0, value=8.0, step=1.0)

        forecast_pct = st.slider("Sales forecast adjustment (%)", min_value=-50, max_value=100, value=0, help="Positive = expect higher sales, negative = lower")

    if st.button("Generate Recommendations", type="primary"):
        with st.spinner("Analyzing inventory..."):
            targets = OrderTargets(default_weeks=target_weeks)
            constraints = OrderConstraints(
                max_spend=max_spend if max_spend > 0 else None,
                low_stock_weeks=low_stock_weeks,
                overstock_weeks=overstock_weeks,
            )
            forecast = SalesForecast(percent_change=forecast_pct) if forecast_pct != 0 else None

            request = RecommendRequest(
                dataset_id=dataset_id,
                targets=targets,
                constraints=constraints,
                forecast=forecast,
            )

            run = order_svc.generate_recommendations(dataset, request)
            st.session_state.last_run = run

    # --- Display results ---
    run = st.session_state.get("last_run")
    if run and run.dataset_id == dataset_id:
        st.divider()

        # Summary
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Items to Order", run.total_items)
        s2.metric("Total Spend", f"${run.total_spend:,.2f}")
        s3.metric("Low Stock", run.low_stock_count)
        s4.metric("Overstock", run.overstock_count)

        # Recommendations table
        if run.recommendations:
            recs_data = []
            for rec in run.recommendations:
                recs_data.append({
                    "Item": rec.item_name,
                    "Category": rec.category or "-",
                    "Vendor": rec.vendor or "-",
                    "On Hand": rec.on_hand,
                    "Avg Usage": round(rec.avg_usage, 1),
                    "Order Qty": rec.suggested_qty,
                    "Unit Cost": f"${rec.unit_cost:.2f}" if rec.unit_cost else "-",
                    "Total": f"${rec.total_cost:.2f}" if rec.total_cost else "-",
                    "Reason": rec.reason.value.replace("_", " ").title(),
                    "Confidence": rec.confidence.value.title(),
                })

            df = pd.DataFrame(recs_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Export CSV
            csv = df.to_csv(index=False)
            st.download_button(
                "Download as CSV",
                csv,
                file_name=f"order_recommendations_{run.run_id}.csv",
                mime="text/csv",
            )

            # By-vendor breakdown
            if run.by_vendor:
                st.subheader("By Vendor")
                vendor_rows = []
                for v, data in run.by_vendor.items():
                    vendor_rows.append({
                        "Vendor": v,
                        "Items": data.get("items", 0),
                        "Spend": f"${data.get('spend', 0):,.2f}",
                    })
                st.dataframe(pd.DataFrame(vendor_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No order recommendations needed - inventory looks good!")


# ===================================================================
# Route to page
# ===================================================================

if page == "Dashboard":
    render_dashboard()
elif page == "Inventory":
    render_inventory()
elif page == "Upload":
    render_upload()
elif page == "Order Recommendations":
    render_orders()
