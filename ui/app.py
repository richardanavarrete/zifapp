"""
HoundCOGS Streamlit Application

Main entry point for the UI. This is a thin client that calls the API.

Run with: streamlit run ui/app.py
"""

import streamlit as st
from datetime import datetime

from ui.config import get_settings
from ui.api_client import get_client, APIResponse
from ui.pages import inventory, orders, cogs, voice

# Page configuration
settings = get_settings()
st.set_page_config(
    page_title=settings.page_title,
    page_icon=settings.page_icon or None,
    layout="wide",
    initial_sidebar_state="expanded",
)


def check_api_connection() -> bool:
    """Check if API is available."""
    client = get_client()
    result = client.health_check()
    return result.success


def show_connection_error():
    """Show API connection error."""
    st.error(
        "Cannot connect to the HoundCOGS API. "
        "Please ensure the API server is running."
    )
    st.info(
        f"Expected API URL: {get_settings().api_base_url}\n\n"
        "Start the API with: `uvicorn api.main:app --reload`"
    )


def main():
    """Main application entry point."""
    # Sidebar navigation
    st.sidebar.title("HoundCOGS")
    st.sidebar.caption("Sniffing out savings!")

    # Check API connection
    api_available = check_api_connection()

    if not api_available:
        show_connection_error()
        return

    # Show API status
    st.sidebar.success("API Connected")

    # Navigation
    page = st.sidebar.radio(
        "Navigate",
        options=[
            "Inventory",
            "Order Recommendations",
            "COGS Analysis",
            "Voice Counting",
            "Settings",
        ],
        index=0,
    )

    st.sidebar.divider()

    # Quick stats in sidebar
    show_sidebar_stats()

    # Render selected page
    if page == "Inventory":
        inventory.render()
    elif page == "Order Recommendations":
        orders.render()
    elif page == "COGS Analysis":
        cogs.render()
    elif page == "Voice Counting":
        voice.render()
    elif page == "Settings":
        render_settings()


def show_sidebar_stats():
    """Show quick stats in sidebar."""
    client = get_client()

    # Get dataset count
    result = client.list_datasets(page=1, page_size=1)
    if result.success and result.data:
        datasets = result.data if isinstance(result.data, list) else []
        st.sidebar.metric("Datasets", len(datasets))


def render_settings():
    """Render settings page."""
    st.title("Settings")

    st.subheader("API Configuration")
    settings = get_settings()

    st.text_input(
        "API Base URL",
        value=settings.api_base_url,
        disabled=True,
        help="Set via UI_API_BASE_URL environment variable"
    )

    api_key_display = "****" + settings.api_key[-4:] if len(settings.api_key) > 4 else "(not set)"
    st.text_input(
        "API Key",
        value=api_key_display,
        disabled=True,
        help="Set via UI_API_KEY environment variable"
    )

    st.divider()

    st.subheader("API Status")
    client = get_client()
    result = client.ready_check()

    if result.success and result.data:
        checks = result.data.get("checks", {})
        for check_name, check_status in checks.items():
            status = check_status.get("status", "unknown")
            if status == "ok" or status == "configured":
                st.success(f"{check_name}: {status}")
            elif status == "not_configured":
                st.info(f"{check_name}: {status}")
            else:
                st.error(f"{check_name}: {status}")


if __name__ == "__main__":
    main()
