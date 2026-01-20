"""
smallCOGS - Main Streamlit Application

A clean inventory tracking UI focused on usage analytics,
voice counting, and smart ordering.
"""

import streamlit as st

from ui.config import UIConfig
from ui.api_client import APIClient, APIError
from ui.pages.dashboard import render_dashboard
from ui.pages.items import render_items_page
from ui.pages.item_detail import render_item_detail
from ui.pages.upload import render_upload_page
from ui.pages.voice import render_voice_page
from ui.pages.orders import render_orders_page

# Page config
st.set_page_config(
    page_title=UIConfig.PAGE_TITLE,
    page_icon=UIConfig.PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)


def get_client() -> APIClient:
    """Get cached API client."""
    if "api_client" not in st.session_state:
        st.session_state.api_client = APIClient()
    return st.session_state.api_client


def main():
    """Main application entry point."""
    client = get_client()

    # Sidebar
    with st.sidebar:
        st.title(f"{UIConfig.PAGE_ICON} {UIConfig.PAGE_TITLE}")
        st.caption("Inventory Usage Tracking")

        st.divider()

        # Navigation
        page = st.radio(
            "Navigation",
            ["Dashboard", "Items", "Voice Counting", "Order Agent", "Upload"],
            label_visibility="collapsed",
        )

        st.divider()

        # Dataset selector (for inventory pages)
        if page in ["Dashboard", "Items", "Order Agent"]:
            try:
                datasets = client.list_datasets()
            except APIError as e:
                st.error(f"API Error: {e}")
                datasets = []
            except Exception as e:
                st.error(f"Cannot connect to API: {e}")
                st.info("Make sure the API is running at " + UIConfig.API_BASE_URL)
                datasets = []

            if datasets:
                dataset_options = {d["name"]: d["dataset_id"] for d in datasets}
                selected_name = st.selectbox(
                    "Select Dataset",
                    options=list(dataset_options.keys()),
                    key="selected_dataset_name",
                )
                selected_dataset_id = dataset_options.get(selected_name)
                st.session_state.selected_dataset_id = selected_dataset_id
            else:
                st.info("No datasets yet. Upload a file to get started.")
                st.session_state.selected_dataset_id = None

        # Debug info
        if UIConfig.SHOW_DEBUG:
            st.divider()
            st.caption(f"API: {UIConfig.API_BASE_URL}")

    # Main content
    dataset_id = st.session_state.get("selected_dataset_id")

    # Check for item detail view
    if st.session_state.get("view_item_id"):
        render_item_detail(client, dataset_id, st.session_state.view_item_id)
        return

    # Route to selected page
    if page == "Dashboard":
        if dataset_id:
            render_dashboard(client, dataset_id)
        else:
            st.info("Select or upload a dataset to view the dashboard.")

    elif page == "Items":
        if dataset_id:
            render_items_page(client, dataset_id)
        else:
            st.info("Select or upload a dataset to view items.")

    elif page == "Voice Counting":
        render_voice_page(client)

    elif page == "Order Agent":
        if dataset_id:
            render_orders_page(client)
        else:
            st.info("Select or upload a dataset to generate recommendations.")

    elif page == "Upload":
        render_upload_page(client)


if __name__ == "__main__":
    main()
