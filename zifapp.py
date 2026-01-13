import streamlit as st
import pandas as pd
from datetime import datetime
from utils import parse_sales_mix_csv, aggregate_all_usage
from statsmodels.tsa.holtwinters import SimpleExpSmoothing
import re
import math
import plotly.express as px
import plotly.graph_objects as go
from models import create_dataset_from_excel
from features import compute_features
from mappings import enrich_dataset
from cogs import (
    calculate_cogs_by_category,
    calculate_cogs_by_vendor,
    calculate_theoretical_cogs,
    calculate_pour_cost,
    calculate_pour_cost_actual,
    calculate_variance_analysis,
    generate_shrinkage_report,
    get_cogs_summary,
    calculate_item_profitability
)
import cache_manager
from policy import OrderTargets

# --- Page Configuration (MUST BE THE FIRST STREAMLIT COMMAND) ---
st.set_page_config(page_title="Bev Usage Analyzer", layout="wide")
st.title("🍺 Bev Usage Analyzer")

# --- Caching the data processing ---
@st.cache_data
def load_and_process_data(uploaded_files, smoothing_level=0.3, trend_threshold=0.1):
    """
    Reads the uploaded Excel files, processes all data, and calculates summary metrics.
    Supports multiple files (e.g., multiple years) to combine historical data.
    This function is cached to prevent re-running on every widget interaction.

    Args:
        uploaded_files: List of uploaded file objects (or single file for backwards compatibility)
        smoothing_level: Alpha parameter for exponential smoothing (default 0.3)
        trend_threshold: Threshold for trend detection (default 0.1)

    Returns:
        summary_df: Summary DataFrame with metrics per item
        vendor_map: Dictionary mapping vendors to their items
        category_map: Dictionary mapping categories to their items
        full_df: Full DataFrame with all weeks from all files
    """
    # Handle single file or multiple files
    if not isinstance(uploaded_files, list):
        uploaded_files = [uploaded_files]

    # Get original order from the first sheet of the first file
    first_xls = pd.ExcelFile(uploaded_files[0])
    first_sheet_names = first_xls.sheet_names
    original_order_df = first_xls.parse(first_sheet_names[0], skiprows=4)
    original_order = original_order_df.iloc[:, 0].dropna().astype(str).tolist()

    # Process all files
    compiled_data = []
    for uploaded_file in uploaded_files:
        try:
            xls = pd.ExcelFile(uploaded_file)
            sheet_names = xls.sheet_names

            for sheet in sheet_names:
                try:
                    df = xls.parse(sheet, skiprows=4)
                    # Rename columns based on index positions
                    df = df.rename(columns={
                        df.columns[0]: 'Item',
                        df.columns[9]: 'Usage',
                        df.columns[7]: 'End Inventory'
                    })
                    df = df[['Item', 'Usage', 'End Inventory']]
                    df['Week'] = sheet
                    df['Source File'] = uploaded_file.name  # Track which file this came from

                    # extract date
                    date_value = xls.parse(sheet).iloc[1, 0]
                    df['Date'] = pd.to_datetime(date_value, errors='coerce')
                    compiled_data.append(df)
                except Exception:
                    continue
        except Exception:
            st.warning(f"⚠️ Error processing file: {uploaded_file.name}")
            continue
            
    full_df = pd.concat(compiled_data, ignore_index=True)
    full_df = full_df.dropna(subset=['Item', 'Usage'])
    full_df['Item'] = full_df['Item'].astype(str).str.strip()
    full_df = full_df[~full_df['Item'].str.upper().str.startswith('TOTAL')]

    full_df['Usage'] = pd.to_numeric(full_df['Usage'], errors='coerce')
    full_df['End Inventory'] = pd.to_numeric(full_df['End Inventory'], errors='coerce')
    full_df = full_df.dropna(subset=['Usage', 'End Inventory'])

    # Remove duplicate (Item, Date) combinations (keep the last occurrence)
    # This handles cases where multiple files have overlapping weeks
    duplicates_before = len(full_df)
    full_df = full_df.drop_duplicates(subset=['Item', 'Date'], keep='last')
    duplicates_removed = duplicates_before - len(full_df)
    if duplicates_removed > 0:
        st.info(f"ℹ️ Removed {duplicates_removed} duplicate entries from overlapping files.")

    # Sort by Item and Date to ensure chronological order
    full_df = full_df.sort_values(by=['Item', 'Date'])

    def compute_metrics(group):
        usage = group['Usage']
        inventory = group['End Inventory']
        dates = group['Date']
        
        last_week_usage = usage.iloc[-1] if not usage.empty else None
        last_10 = usage.tail(10)
        last_4 = usage.tail(4)
        last_2 = usage.tail(2)
        
        # Calculate YTD based on the most recent year in the data, not current calendar year
        if pd.api.types.is_datetime64_any_dtype(dates) and not dates.empty:
            most_recent_year = dates.max().year
            ytd_avg = group[dates.dt.year == most_recent_year]['Usage'].mean()
        else:
            ytd_avg = None
        
        def safe_div(n, d):
            if pd.notna(d) and d > 0:
                return round(n / d, 2)
            return None
            
        avg_of_highest_4 = usage.nlargest(4).mean() if not usage.empty else None
        non_zero_usage = usage[usage > 0]
        avg_of_lowest_4_non_zero = non_zero_usage.nsmallest(4).mean() if not non_zero_usage.empty else None
        
        # Trend calculation
        trend_indicator = "→"
        if len(usage) >= 4:
            try:
                model = SimpleExpSmoothing(usage.values).fit(smoothing_level=smoothing_level, optimized=False)
                smoothed_current = model.fittedvalues[-1]
                baseline = usage.mean()
                if baseline > 0:
                    ratio = smoothed_current / baseline
                    if ratio > (1 + trend_threshold):
                        trend_indicator = "↑"
                    elif ratio < (1 - trend_threshold):
                        trend_indicator = "↓"
            except Exception:
                trend_indicator = "→"
                
        return pd.Series({
            'Trend': trend_indicator,
            'On Hand': round(inventory.iloc[-1], 2),
            'Last Week Usage': round(last_week_usage, 2) if pd.notna(last_week_usage) else None,
            'Year-to-Date Average': round(ytd_avg, 2) if pd.notna(ytd_avg) else None,
            '10-Week Average': round(last_10.mean(), 2) if not last_10.empty else None,
            '4-Week Average': round(last_4.mean(), 2) if not last_4.empty else None,
            '2-Week Average': round(last_2.mean(), 2) if not last_2.empty else None,
            'All-Time High': round(usage.max(), 2),
            'Lowest 4 Average (non-zero)': round(avg_of_lowest_4_non_zero, 2) if pd.notna(avg_of_lowest_4_non_zero) else None,
            'Highest 4 Average': round(avg_of_highest_4, 2) if pd.notna(avg_of_highest_4) else None,
            'Weeks Remaining (YTD)': safe_div(inventory.iloc[-1], ytd_avg),
            'Weeks Remaining (10 Wk)': safe_div(inventory.iloc[-1], last_10.mean()),
            'Weeks Remaining (4 Wk)': safe_div(inventory.iloc[-1], last_4.mean()),
            'Weeks Remaining (2 Wk)': safe_div(inventory.iloc[-1], last_2.mean()),
            'Weeks Remaining (ATH)': safe_div(inventory.iloc[-1], usage.max()),
            'Weeks Remaining (Lowest 4)': safe_div(inventory.iloc[-1], avg_of_lowest_4_non_zero),
            'Weeks Remaining (Highest 4)': safe_div(inventory.iloc[-1], avg_of_highest_4)
        })

    summary_df = full_df.groupby('Item').apply(compute_metrics).reset_index()
    summary_df['Item'] = summary_df['Item'].astype(str)
    
    # Sort based on original order
    original_order_cleaned = [item.strip() for item in original_order]
    summary_df['ItemOrder'] = summary_df['Item'].apply(
        lambda x: original_order_cleaned.index(x) if x in original_order_cleaned else float('inf')
    )
    summary_df = summary_df.sort_values(by='ItemOrder').drop(columns='ItemOrder')
    
    # Define Vendor Map
    vendor_map = {
        "Breakthru": ["WHISKEY Buffalo Trace", "WHISKEY Bulleit Straight Rye", "WHISKEY Crown Royal", "WHISKEY Crown Royal Regal Apple", "WHISKEY Fireball Cinnamon", "WHISKEY Jack Daniels Black", "WHISKEY Jack Daniels Tennessee Fire", "VODKA Deep Eddy Lime", "VODKA Deep Eddy Orange", "VODKA Deep Eddy Ruby Red", "VODKA Fleischmann's Cherry", "VODKA Fleischmann's Grape", "VODKA Ketel One", "LIQ Amaretto", "LIQ Baileys Irish Cream", "LIQ Chambord", "LIQ Melon", "LIQ Rumpleminze", "LIQ Triple Sec", "LIQ Blue Curacao", "LIQ Butterscotch", "LIQ Peach Schnapps", "LIQ Sour Apple", "LIQ Watermelon Schnapps", "BRANDY Well", "GIN Well", "RUM Well", "SCOTCH Well", "TEQUILA Well", "VODKA Well", "WHISKEY Well", "GIN Tanqueray", "TEQUILA Casamigos Blanco", "TEQUILA Corazon Reposado", "TEQUILA Don Julio Blanco", "RUM Captain Morgan Spiced", "WINE LaMarca Prosecco", "WINE William Wycliff Brut Chateauamp", "BAR CONS Bloody Mary", "JUICE Red Bull", "JUICE Red Bull SF", "JUICE Red Bull Yellow"],
        "Southern": ["WHISKEY Basil Hayden", "WHISKEY Jameson", "WHISKEY Jim Beam", "WHISKEY Makers Mark", "WHISKEY Skrewball Peanut Butter", "VODKA Grey Goose", "VODKA Titos", "TEQUILA Cazadores Reposado", "TEQUILA Patron Silver", "RUM Bacardi Superior White", "RUM Malibu Coconut", "WHISKEY Dewars White Label", "WHISKEY Glenlivet", "LIQ Grand Marnier", "LIQ Jagermeister", "LIQ Kahlua", "LIQ Vermouth Dry", "LIQ Vermouth Sweet", "WINE Kendall Jackson Chardonnay", "WINE La Crema Chardonnay", "WINE La Crema Pinot Noir", "WINE Troublemaker Red", "WINE Villa Sandi Pinot Grigio", "BAR CONS Bitters", "BAR CONS Simple Syrup"],
        "RNDC": ["WHISKEY Four Roses", "GIN Hendricks", "TEQUILA Milagro Anejo", "TEQUILA Milagro Reposado", "TEQUILA Milagro Silver", "WINE Infamous Goose Sauv Blanc", "WINE Salmon Creek Cab", "WINE Salmon Creek Chard", "WINE Salmon Creek Merlot", "WINE Salmon Creek White Zin", "BAR CONS Mango Puree"],
        "Crescent": ["BEER DFT Alaskan Amber", "BEER DFT Blue Moon Belgian White", "BEER DFT Coors Light", "BEER DFT Dos Equis Lager", "BEER DFT Miller Lite", "BEER DFT Modelo Especial", "BEER DFT New Belgium Juicy Haze IPA", "BEER BTL Coors Banquet", "BEER BTL Coors Light", "BEER BTL Miller Lite", "BEER BTL Angry Orchard Crisp Apple", "BEER BTL College Street Big Blue Van", "BEER BTL Corona NA", "BEER BTL Corona Extra", "BEER BTL Corona Premier", "BEER BTL Coronita Extra", "BEER BTL Dos Equis Lager", "BEER BTL Guinness", "BEER BTL Heineken 0.0", "BEER BTL Modelo Especial", "BEER BTL Pacifico", "BEER BTL Truly Pineapple", "BEER BTL Truly Wild Berry", "BEER BTL Twisted Tea", "BEER BTL White Claw Black Cherry", "BEER BTL White Claw Mango", "BEER BTL White Claw Peach", "JUICE Ginger Beer", "VODKA Western Son Blueberry", "VODKA Western Son Lemon", "VODKA Western Son Original", "VODKA Western Son Prickly Pear", "VODKA Western Son Raspberry"],
        "Hensley": ["BEER DFT Bud Light", "BEER DFT Church Music", "BEER DFT Firestone Walker 805", "BEER DFT Michelob Ultra", "BEER DFT Mother Road Sunday Drive", "BEER DFT Mother Road Tower Station", "BEER BTL Bud Light", "BEER BTL Budweiser", "BEER BTL Michelob Ultra", "BEER BTL Austin Eastciders"]
    }
    # Clean vendor map items
    for vendor, items in vendor_map.items():
        vendor_map[vendor] = [item.strip() for item in items]
        
    # Define Category Map based on keywords
    category_map = {cat: [] for cat in ["Well", "Whiskey", "Vodka", "Gin", "Tequila", "Rum", "Scotch", "Liqueur", "Cordials", "Wine", "Draft Beer", "Bottled Beer", "Juice", "Bar Consumables"]}
    for item in summary_df['Item']:
        upper_item = item.upper().strip()
        if "WELL" in upper_item: category_map["Well"].append(item)
        elif "WHISKEY" in upper_item: category_map["Whiskey"].append(item)
        elif "VODKA" in upper_item: category_map["Vodka"].append(item)
        elif "GIN" in upper_item: category_map["Gin"].append(item)
        elif "TEQUILA" in upper_item: category_map["Tequila"].append(item)
        elif "RUM" in upper_item: category_map["Rum"].append(item)
        elif "SCOTCH" in upper_item: category_map["Scotch"].append(item)
        elif "LIQ" in upper_item and "SCHNAPPS" not in upper_item: category_map["Liqueur"].append(item)
        elif "SCHNAPPS" in upper_item: category_map["Cordials"].append(item)
        elif "WINE" in upper_item: category_map["Wine"].append(item)
        elif "BEER DFT" in upper_item: category_map["Draft Beer"].append(item)
        elif "BEER BTL" in upper_item: category_map["Bottled Beer"].append(item)
        elif "JUICE" in upper_item: category_map["Juice"].append(item)
        elif "BAR CONS" in upper_item: category_map["Bar Consumables"].append(item)
        
    return summary_df, vendor_map, category_map, full_df


@st.cache_data
def load_cogs_data(uploaded_files):
    """
    Load COGS data using the new models and features modules.

    Args:
        uploaded_files: List of uploaded file objects

    Returns:
        dataset: InventoryDataset with cost data
        features_df: Features DataFrame with COGS metrics
    """
    # Create dataset using new models module (extracts cost data)
    dataset = create_dataset_from_excel(uploaded_files)

    # Enrich dataset with vendor and category mappings
    dataset = enrich_dataset(dataset)

    # Compute features including COGS metrics
    features_df = compute_features(dataset)

    return dataset, features_df


# --- Main App UI ---

# Initialize session_state for uploaded files
if 'bevweekly_files' not in st.session_state:
    st.session_state.bevweekly_files = None
if 'sales_mix_file' not in st.session_state:
    st.session_state.sales_mix_file = None

# File uploader returns new files on change, None if unchanged
uploaded_files_widget = st.file_uploader(
    "Upload your BEVWEEKLY Excel Files (you can select multiple years)",
    type="xlsx",
    accept_multiple_files=True,
    help="Hold Ctrl/Cmd to select multiple files, or drag & drop multiple files. Upload multiple years (e.g., 2026, 2025, 2024) to see historical trends."
)

# Update session_state if new files uploaded
if uploaded_files_widget is not None:
    st.session_state.bevweekly_files = uploaded_files_widget

# Work with session_state version
uploaded_files = st.session_state.bevweekly_files

if uploaded_files:
    # Show file summary
    st.info(f"**{len(uploaded_files)} file(s) uploaded**")
    cols = st.columns(min(len(uploaded_files), 4))  # Max 4 columns for readability
    for idx, file in enumerate(uploaded_files):
        with cols[idx % 4]:
            try:
                sheet_count = len(pd.ExcelFile(file).sheet_names)
                st.metric(
                    label=file.name,
                    value=f"{sheet_count} weeks"
                )
            except Exception:
                st.metric(label=file.name, value="Error")

    with st.expander("Trend Settings", expanded=False):
        smoothing_level = st.slider("Smoothing Level (α)", 0.1, 0.9, 0.3, 0.05)
        trend_threshold = st.slider("Trend Threshold", 0.05, 0.30, 0.10, 0.05)

    # Sales Mix upload (shared across Sales Mix Analysis and Pour Cost tabs)
    st.markdown("---")
    st.subheader("📊 Sales Mix Data (Optional)")
    st.markdown("Upload your Sales Mix CSV for Pour Cost & Variance Analysis. This data will be available in both the Sales Mix Analysis and Pour Cost tabs.")

    sales_mix_widget = st.file_uploader(
        "Upload Sales Mix CSV",
        type="csv",
        key="sales_mix_upload_main",
        help="Upload your GEMpos Sales Mix CSV file to calculate theoretical usage and pour costs."
    )

    if sales_mix_widget is not None:
        st.session_state.sales_mix_file = sales_mix_widget
        st.success(f"✅ Sales Mix file uploaded: {sales_mix_widget.name}")

    # Check for cached data
    st.markdown("---")
    file_hash = cache_manager.get_file_hash(uploaded_files)
    use_cache = False
    cached_data = None

    if cache_manager.is_cached(file_hash, 'bevweekly'):
        cache_info = cache_manager.get_cache_info()
        use_cache = st.checkbox(
            "📦 Found cached data from a previous session. Load from cache?",
            value=True,
            help=f"Skip parsing and load pre-processed data (faster). Cache directory: {cache_info['cache_dir']}"
        )

        if use_cache:
            with st.spinner("Loading from cache..."):
                cached_data = cache_manager.load_from_cache(file_hash, 'bevweekly')

            if cached_data:
                st.success(f"✅ Loaded from cache! (Cached at: {cached_data.get('cached_at', 'unknown')})")
            else:
                st.warning("⚠️ Cache load failed. Processing fresh data...")
                use_cache = False

    try:
        # Use cached data if available, otherwise process fresh
        if use_cache and cached_data:
            summary_df = cached_data['summary_df']
            full_df = cached_data['full_df']
            features_df = cached_data['features_df']
            dataset = cached_data['dataset']
            vendor_map = cached_data['vendor_map']
            category_map = cached_data['category_map']
        else:
            # Process data fresh
            summary_df, vendor_map, category_map, full_df = load_and_process_data(uploaded_files, smoothing_level, trend_threshold)

            # Load COGS data using new models
            dataset, features_df = load_cogs_data(uploaded_files)

            # Save to cache for next time
            cache_manager.save_to_cache(file_hash, {
                'summary_df': summary_df,
                'full_df': full_df,
                'features_df': features_df,
                'dataset': dataset,
                'vendor_map': vendor_map,
                'category_map': category_map
            }, 'bevweekly')

        # Show combined data summary
        if not full_df.empty and 'Date' in full_df.columns:
            total_weeks = full_df['Week'].nunique()
            date_range_start = full_df['Date'].min().strftime('%m/%d/%Y')
            date_range_end = full_df['Date'].max().strftime('%m/%d/%Y')
            unique_items = full_df['Item'].nunique()

            st.success("✅ Data loaded successfully!")
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Weeks Loaded", total_weeks)
            col2.metric("Date Range", f"{date_range_start} - {date_range_end}")
            col3.metric("Unique Items", unique_items)

    except Exception as e:
        st.error(f"An error occurred during data processing: {e}")
        st.stop()

    tab_summary, tab_ordering_worksheet, tab_sales_mix, tab_trends, tab_cogs, tab_pour_cost, tab_excess_inventory = st.tabs([
        "📊 Summary",
        "🧪 Ordering Worksheet",
        "Sales Mix Analysis",
        "📈 Item Trends",
        "💰 COGS Analysis",
        "📊 Pour Cost",
        "📦 Excess Inventory"
    ])

    # --- TAB 1: SUMMARY ---
    with tab_summary:
        st.subheader("Usage Summary")

        # Week selector
        st.markdown("### 📅 Select Week to View")
        all_weeks = dataset.get_all_cogs_summaries() if dataset else []

        # Add "All Weeks" option for aggregate view
        week_options = {"All Weeks (Aggregate)": None}

        if all_weeks:
            for summary in all_weeks:
                week_label = f"{summary.week_name} ({summary.week_date.strftime('%Y-%m-%d')})"
                if summary.is_complete:
                    week_label += " ✅"
                else:
                    week_label += " ⚠️ Incomplete"
                week_options[week_label] = summary.week_name

        selected_week_label = st.selectbox(
            "Select Week",
            options=list(week_options.keys()),
            index=0,  # Default to "All Weeks"
            help="Choose 'All Weeks' for aggregate metrics across all weeks, or select a specific week to see that week's data.",
            key="summary_week_selector"
        )

        selected_week = week_options[selected_week_label]

        # Filter summary_df to selected week if specific week chosen
        if selected_week:
            # Filter dataset.records to selected week and recalculate summary
            week_records = dataset.records[dataset.records['week_name'] == selected_week]
            st.info(f"Showing data for: {selected_week_label}")
        else:
            st.info("Showing aggregate data across all weeks")

        st.markdown("---")

        filter_type = st.radio("Filter By:", ["Vendor", "Category"], horizontal=True, key="summary_filter_type")
        display_df = summary_df
        download_filename = "beverage_summary_full.csv"

        if filter_type == "Vendor":
            vendor_options = ["All Vendors"] + list(vendor_map.keys())
            selected_vendor = st.selectbox("Select Vendor", options=vendor_options, key="summary_vendor_select")
            if selected_vendor != "All Vendors":
                display_df = summary_df[summary_df['Item'].isin(vendor_map.get(selected_vendor, []))]
                download_filename = f"beverage_summary_{selected_vendor}.csv"
        elif filter_type == "Category":
            category_options = ["All Categories"] + list(category_map.keys())
            selected_category = st.selectbox("Select Category", options=category_options, key="summary_category_select")
            if selected_category != "All Categories":
                display_df = summary_df[summary_df['Item'].isin(category_map.get(selected_category, []))]
                download_filename = f"beverage_summary_{selected_category}.csv"
                
        threshold = st.slider("Highlight if weeks remaining is below:", 0.2, 10.0, 2.0, 0.1)
        
        def highlight_weeks_remaining(val, threshold=2.0):
            if pd.notna(val) and isinstance(val, (int, float)) and val < threshold:
                return 'background-color: #ff4b4b'
            return ''

        format_dict = {col: '{:,.2f}' for col in display_df.select_dtypes(include=['float64', 'float32']).columns}
        styled_df = display_df.style.format(format_dict, na_rep="-").applymap(
            highlight_weeks_remaining, 
            threshold=threshold, 
            subset=['Weeks Remaining (YTD)', 'Weeks Remaining (10 Wk)', 'Weeks Remaining (4 Wk)']
        )
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        csv = display_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Summary CSV", data=csv, file_name=download_filename)

    # --- TAB 2: ORDERING WORKSHEET ---
    with tab_ordering_worksheet:
        st.subheader("🧪 Ordering Worksheet: Inventory Planning")

        # Week selector for planning basis
        st.markdown("### 📅 Select Week for Planning")
        all_weeks = dataset.get_all_cogs_summaries() if dataset else []

        # Add "All Weeks" option for aggregate planning
        week_options = {"All Weeks (Aggregate)": None}

        if all_weeks:
            for summary in all_weeks:
                week_label = f"{summary.week_name} ({summary.week_date.strftime('%Y-%m-%d')})"
                if summary.is_complete:
                    week_label += " ✅"
                else:
                    week_label += " ⚠️ Incomplete"
                week_options[week_label] = summary.week_name

        selected_week_label = st.selectbox(
            "Select Week",
            options=list(week_options.keys()),
            index=0,  # Default to "All Weeks"
            help="Choose 'All Weeks' to plan based on aggregate usage averages, or select a specific week to base planning on that week's patterns.",
            key="ordering_week_selector"
        )

        selected_week = week_options[selected_week_label]

        if selected_week:
            st.info(f"Planning based on: {selected_week_label}")
        else:
            st.info("Planning based on aggregate usage across all weeks")

        st.markdown("---")

        mode = st.selectbox("Select View Mode:", ["By Vendor", "By Category"])
        
        usage_option = st.selectbox(
            "Select usage average for calculation:",
            options=['10-Week Average', '4-Week Average', '2-Week Average', 'Year-to-Date Average', 'Lowest 4 Average (non-zero)', 'Highest 4 Average'],
            index=1,
            key="usage_radio"
        )

        def render_worksheet_table(items_to_display, key_prefix):
            worksheet_state_key = f"worksheet_df_{key_prefix}"
            usage_state_key = f"usage_option_{key_prefix}"

            # Master slider and Apply button
            st.markdown("---")
            col1, col2 = st.columns([3, 1])
            with col1:
                bulk_week_target = st.slider(f"Set a target for all items in {key_prefix}:", 0.0, 12.0, 4.0, 0.1, key=f"slider_{key_prefix}")
            with col2:
                st.write("")
                if st.button("Apply to All", use_container_width=True, key=f"button_{key_prefix}"):
                    if worksheet_state_key in st.session_state:
                        df_to_update = st.session_state[worksheet_state_key].copy()
                        df_to_update['Target Weeks of Supply'] = bulk_week_target
                        df_to_update['Order Qty (Bottles)'] = df_to_update.apply(
                            lambda r: max(0, int(math.ceil((r['Target Weeks of Supply'] * r['Selected Avg']) - r['On Hand']))) if r['Selected Avg'] > 0 else 0, 
                            axis=1
                        )
                        st.session_state[worksheet_state_key] = df_to_update
                        st.rerun()

            # Initialize session state for this tab's dataframe
            if worksheet_state_key not in st.session_state or st.session_state.get(usage_state_key) != usage_option:
                filtered_df = summary_df[summary_df['Item'].isin(items_to_display)]
                editor_df_data = {
                    'Item': filtered_df['Item'],
                    'On Hand': filtered_df['On Hand'],
                    'Selected Avg': filtered_df[usage_option],
                    'Order Qty (Bottles)': 0,
                    'Target Weeks of Supply': 0.0
                }
                worksheet_df = pd.DataFrame(editor_df_data).reset_index(drop=True)
                worksheet_df['Selected Avg'] = pd.to_numeric(worksheet_df['Selected Avg'], errors='coerce').fillna(0)
                
                def temp_safe_div(n, d):
                    return round(n / d, 1) if d and pd.notna(d) and d > 0 else 0.0
                    
                worksheet_df['Current Wks Left'] = worksheet_df.apply(lambda row: temp_safe_div(row['On Hand'], row['Selected Avg']), axis=1)
                st.session_state[worksheet_state_key] = worksheet_df[['Item', 'On Hand', 'Current Wks Left', 'Selected Avg', 'Order Qty (Bottles)', 'Target Weeks of Supply']]
                st.session_state[usage_state_key] = usage_option

            # The Data Editor
            edited_df = st.data_editor(
                st.session_state[worksheet_state_key],
                hide_index=True,
                use_container_width=True,
                key=f"editor_{key_prefix}",
                column_config={
                    "Item": st.column_config.TextColumn(disabled=True),
                    "On Hand": st.column_config.NumberColumn(format="%.2f", disabled=True),
                    "Current Wks Left": st.column_config.NumberColumn(format="%.1f", disabled=True),
                    "Selected Avg": st.column_config.NumberColumn("Avg Usage", format="%.2f", disabled=True),
                    "Order Qty (Bottles)": st.column_config.NumberColumn(min_value=0, step=1, format="%d"),
                    "Target Weeks of Supply": st.column_config.NumberColumn(min_value=0.0, step=0.1, format="%.1f")
                }
            )

            # Recalculate if edited
            if not edited_df.equals(st.session_state[worksheet_state_key]):
                # Logic to determine if Bottles or Weeks were edited would go here
                # For simplicity in this clean version, we update session state directly
                st.session_state[worksheet_state_key] = edited_df
                # (You can add the specific reactive logic here if you want bottles to update weeks or vice versa)
                # st.rerun() # Uncomment if you want immediate recalculation

            # Generate Final Order Summary Button
            if st.button("Generate Final Order Summary", key=f"finalize_{key_prefix}"):
                order_df = st.session_state[worksheet_state_key]
                items_to_order = order_df[order_df['Order Qty (Bottles)'] > 0]
                if not items_to_order.empty:
                    st.dataframe(items_to_order, use_container_width=True)
                else:
                    st.warning("No items marked for order.")

            # Keg Counter Logic
            if key_prefix in ["Crescent", "Hensley", "Draft Beer"]:
                current_order_df = st.session_state.get(worksheet_state_key, pd.DataFrame())
                if not current_order_df.empty:
                    draft_items = category_map.get("Draft Beer", [])
                    kegs = current_order_df[current_order_df['Item'].isin(draft_items)]
                    st.metric("Total Kegs to Order", f"{kegs['Order Qty (Bottles)'].sum():,.0f}")

        # Render the views
        if mode == "By Vendor":
            vendor_keys = list(vendor_map.keys())
            vendor_tabs = st.tabs(vendor_keys)
            for i, tab in enumerate(vendor_tabs):
                with tab:
                    render_worksheet_table(vendor_map.get(vendor_keys[i], []), vendor_keys[i])
        else:
            category_keys = list(category_map.keys())
            category_tabs = st.tabs(category_keys)
            for i, tab in enumerate(category_tabs):
                with tab:
                    render_worksheet_table(category_map.get(category_keys[i], []), category_keys[i])

    # --- TAB 3: SALES MIX ANALYSIS ---
    with tab_sales_mix:
        st.subheader("📈 Sales Mix Analysis: Theoretical vs Actual Usage")
        st.markdown("""
        Compare your actual inventory usage against theoretical usage based on sales data.
        Identify variances that may indicate waste, over-pouring, theft, or other issues.
        """)

        # Week selector for variance comparison
        st.markdown("### 📅 Select Week to Compare")
        all_weeks = dataset.get_all_cogs_summaries() if dataset else []

        if all_weeks:
            week_options = {}
            for summary in all_weeks:
                week_label = f"{summary.week_name} ({summary.week_date.strftime('%Y-%m-%d')})"
                if summary.is_complete:
                    week_label += " ✅"
                else:
                    week_label += " ⚠️ Incomplete"
                week_options[week_label] = summary.week_name

            # Default to latest complete week
            latest_complete = dataset.get_latest_complete_cogs_summary()
            default_week_name = latest_complete.week_name if latest_complete else all_weeks[0].week_name
            default_label = next((label for label, name in week_options.items() if name == default_week_name), list(week_options.keys())[0])

            selected_week_label = st.selectbox(
                "Select Week",
                options=list(week_options.keys()),
                index=list(week_options.keys()).index(default_label),
                help="Choose which week's actual usage data to compare against theoretical usage.",
                key="sales_mix_week_selector"
            )

            selected_week = week_options[selected_week_label]
            st.info(f"Comparing theoretical usage against actual usage from: {selected_week_label}")
        else:
            selected_week = None
            st.info("Using most recent week's actual usage data")

        st.markdown("---")

        # Get sales_mix_file from session_state (uploaded at top level)
        sales_mix_file = st.session_state.sales_mix_file

        if sales_mix_file is None:
            st.info("⬆️ Please upload a Sales Mix CSV file at the top of the page to use this feature.")

        if sales_mix_file:
            try:
                sales_df = parse_sales_mix_csv(sales_mix_file)

                if sales_df is not None and not sales_df.empty:
                    st.success(f"✅ Parsed {len(sales_df)} line items from Sales Mix")

                    with st.expander("View Parsed Sales Data", expanded=False):
                        st.dataframe(sales_df, use_container_width=True, hide_index=True)

                    # DEBUG: Show exact item names for mapping
                    with st.expander("🔍 DEBUG: Exact Item Names from POS", expanded=False):
                        st.markdown("**Use these EXACT names in your mappings:**")
                        liquor_items = sales_df[sales_df['Category'] == 'Liquor']['Item'].unique()
                        st.code('\n'.join([f'"{item}"' for item in sorted(liquor_items)]))

                    # Calculate theoretical usage
                    all_usage, unmatched_items, total_revenue = aggregate_all_usage(sales_df)
                    
                    usage_data = []
                    for inv_item, data in all_usage.items():
                        row = {
                            'Inventory Item': inv_item,
                            'Theoretical Usage': data['theoretical_usage'],
                            'Unit': data['unit'],
                        }
                        actual_row = summary_df[summary_df['Item'] == inv_item]
                        if not actual_row.empty:
                            actual_usage = actual_row['Last Week Usage'].values[0]
                            row['Actual Usage (Last Week)'] = actual_usage if pd.notna(actual_usage) else None
                            if pd.notna(actual_usage) and actual_usage > 0:
                                variance = data['theoretical_usage'] - actual_usage
                                variance_pct = (variance / actual_usage) * 100
                                row['Variance'] = round(variance, 2)
                                row['Variance %'] = round(variance_pct, 1)
                            else:
                                row['Variance'] = None
                                row['Variance %'] = None
                        else:
                            row['Actual Usage (Last Week)'] = None
                            row['Variance'] = None
                            row['Variance %'] = None
                        usage_data.append(row)
                    
                    usage_df = pd.DataFrame(usage_data)
                    
                    st.markdown("---")
                    col1, col2 = st.columns(2)
                    with col1:
                        category_filter = st.selectbox(
                            "Filter by Category:",
                            ["All", "Draft Beer", "Bottled Beer", "Liquor", "Wine", "Bar Consumables"],
                            key="sales_mix_category_filter"
                        )
                    with col2:
                        show_variance_only = st.checkbox("Show only items with variance data", value=False)
                    
                    display_usage_df = usage_df.copy()
                    
                    if category_filter != "All":
                        if category_filter == "Draft Beer":
                            display_usage_df = display_usage_df[display_usage_df['Inventory Item'].str.contains('BEER DFT')]
                        elif category_filter == "Bottled Beer":
                            display_usage_df = display_usage_df[display_usage_df['Inventory Item'].str.contains('BEER BTL')]
                        elif category_filter == "Liquor":
                            display_usage_df = display_usage_df[
                                display_usage_df['Inventory Item'].str.contains('WHISKEY|VODKA|GIN|TEQUILA|RUM|SCOTCH|LIQ', regex=True)
                            ]
                        elif category_filter == "Wine":
                            display_usage_df = display_usage_df[display_usage_df['Inventory Item'].str.contains('WINE')]
                        elif category_filter == "Bar Consumables":
                            display_usage_df = display_usage_df[
                                display_usage_df['Inventory Item'].str.contains('BAR CONS|JUICE', regex=True)
                            ]
                    
                    if show_variance_only:
                        display_usage_df = display_usage_df[display_usage_df['Variance'].notna()]
                    
                    def highlight_variance(val):
                        if pd.isna(val):
                            return ''
                        if val > 10:
                            return 'background-color: #ffcccb'
                        elif val < -10:
                            return 'background-color: #90EE90'
                        return ''
                    
                    st.markdown("### Theoretical Usage Results")
                    st.markdown("""
                    **Variance Interpretation:**
                    - 🔴 **Positive variance (red):** Theoretical > Actual — You should have used more than you did. 
                      Possible: theft, waste, spillage, or inventory count error.
                    - 🟢 **Negative variance (green):** Theoretical < Actual — You used more than sales suggest. 
                      Possible: over-ringing, comps not tracked, or heavy pours.
                    """)
                    
                    if not display_usage_df.empty:
                        styled_usage = display_usage_df.style.applymap(
                            highlight_variance, subset=['Variance %']
                        ).format({
                            'Theoretical Usage': '{:.2f}',
                            'Actual Usage (Last Week)': '{:.2f}',
                            'Variance': '{:.2f}',
                            'Variance %': '{:.1f}%'
                        }, na_rep="-")
                        
                        st.dataframe(styled_usage, use_container_width=True, hide_index=True)
                        
                        csv_usage = display_usage_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            "Download Usage Analysis CSV",
                            data=csv_usage,
                            file_name="sales_mix_usage_analysis.csv"
                        )
                    else:
                        st.warning("No data to display with current filters.")
                    
                    if unmatched_items:
                        with st.expander(f"⚠️ Unmatched Items ({len(unmatched_items)})", expanded=False):
                            st.markdown("These items could not be mapped to inventory:")
                            for item in unmatched_items:
                                st.write(f"- {item}")
                    
                    with st.expander("📋 Detailed Calculation Breakdown", expanded=False):
                        for inv_item, data in all_usage.items():
                            if data.get('details'):
                                st.markdown(f"**{inv_item}** ({data['theoretical_usage']:.2f} {data['unit']})")
                                for detail in data['details']:
                                    st.write(f"  - {detail}")
                                st.markdown("---")
                
            except Exception as e:
                st.error(f"Error processing Sales Mix: {e}")
                import traceback
                st.code(traceback.format_exc())
        else:
            st.info("👆 Upload a Sales Mix CSV to begin analysis.")

    # --- TAB 4: ITEM TRENDS ---
    with tab_trends:
        st.subheader("📈 Item Trends Visualization")
        st.markdown("Select an item to view its historical usage trends over time.")

        # Week selector for specific week analysis
        st.markdown("### 📅 Select Week to Highlight")
        all_weeks = dataset.get_all_cogs_summaries() if dataset else []

        # Add "All Weeks" option to show full trend
        week_options = {"All Weeks (Full Trend)": None}

        if all_weeks:
            for summary in all_weeks:
                week_label = f"{summary.week_name} ({summary.week_date.strftime('%Y-%m-%d')})"
                if summary.is_complete:
                    week_label += " ✅"
                else:
                    week_label += " ⚠️ Incomplete"
                week_options[week_label] = summary.week_name

        selected_week_label = st.selectbox(
            "Select Week",
            options=list(week_options.keys()),
            index=0,  # Default to "All Weeks"
            help="Choose 'All Weeks' to see full trend line, or select a specific week to highlight that week's data point.",
            key="trends_week_selector"
        )

        selected_week = week_options[selected_week_label]

        if selected_week:
            st.info(f"Highlighting week: {selected_week_label}")
        else:
            st.info("Showing full trend across all weeks")

        st.markdown("---")

        # Item selector and date range in columns
        col1, col2 = st.columns([2, 1])

        with col1:
            # Get all unique items sorted
            all_items = sorted(summary_df['Item'].unique().tolist())
            selected_item = st.selectbox(
                "Select Item:",
                options=all_items,
                key="trends_item_selector"
            )

        with col2:
            date_range_option = st.selectbox(
                "Date Range:",
                options=["All Available Data", "Last 4 Weeks", "Last 10 Weeks", "Last 6 Months", "Year to Date"],
                key="trends_date_range"
            )

        if selected_item:
            # Filter data for selected item
            item_data = full_df[full_df['Item'] == selected_item].copy()
            item_data = item_data.sort_values('Date')

            # Apply date range filter
            if date_range_option != "All Available Data" and not item_data.empty:
                latest_date = item_data['Date'].max()
                if date_range_option == "Last 4 Weeks":
                    cutoff_date = latest_date - pd.Timedelta(weeks=4)
                    item_data = item_data[item_data['Date'] >= cutoff_date]
                elif date_range_option == "Last 10 Weeks":
                    cutoff_date = latest_date - pd.Timedelta(weeks=10)
                    item_data = item_data[item_data['Date'] >= cutoff_date]
                elif date_range_option == "Last 6 Months":
                    cutoff_date = latest_date - pd.Timedelta(days=180)
                    item_data = item_data[item_data['Date'] >= cutoff_date]
                elif date_range_option == "Year to Date":
                    if pd.api.types.is_datetime64_any_dtype(item_data['Date']):
                        most_recent_year = latest_date.year
                        item_data = item_data[item_data['Date'].dt.year == most_recent_year]

            if not item_data.empty:
                # Get summary stats for this item
                item_summary = summary_df[summary_df['Item'] == selected_item].iloc[0]

                # Display key metrics in columns
                st.markdown("---")
                metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

                with metric_col1:
                    trend_emoji = item_summary['Trend']
                    st.metric("Trend", trend_emoji, help="↑ Increasing | → Stable | ↓ Decreasing")

                with metric_col2:
                    last_week = item_summary['Last Week Usage']
                    st.metric("Last Week Usage", f"{last_week:.2f}" if pd.notna(last_week) else "N/A")

                with metric_col3:
                    # Show the appropriate average based on date range
                    if date_range_option == "Last 4 Weeks":
                        avg_val = item_summary['4-Week Average']
                        avg_label = "4-Week Avg"
                    elif date_range_option == "Last 10 Weeks":
                        avg_val = item_summary['10-Week Average']
                        avg_label = "10-Week Avg"
                    elif date_range_option == "Year to Date":
                        avg_val = item_summary['Year-to-Date Average']
                        avg_label = "YTD Avg"
                    else:
                        avg_val = item_data['Usage'].mean()
                        avg_label = "Average"
                    st.metric(avg_label, f"{avg_val:.2f}" if pd.notna(avg_val) else "N/A")

                with metric_col4:
                    on_hand = item_summary['On Hand']
                    st.metric("On Hand", f"{on_hand:.2f}" if pd.notna(on_hand) else "N/A")

                st.markdown("---")

                # Create the main line chart
                fig = px.line(
                    item_data,
                    x='Date',
                    y='Usage',
                    title=f'{selected_item} - Weekly Usage Trend',
                    markers=True,
                    labels={'Usage': 'Usage (Bottles/Units)', 'Date': 'Week'}
                )

                # Customize the chart
                fig.update_traces(
                    line_color='#1f77b4',
                    marker=dict(size=8, line=dict(width=1, color='white'))
                )

                fig.update_layout(
                    hovermode='x unified',
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(
                        showgrid=True,
                        gridcolor='rgba(128,128,128,0.2)',
                        title_font=dict(size=14)
                    ),
                    yaxis=dict(
                        showgrid=True,
                        gridcolor='rgba(128,128,128,0.2)',
                        title_font=dict(size=14)
                    ),
                    title_font=dict(size=18),
                    height=500
                )

                # Display the chart
                st.plotly_chart(fig, use_container_width=True)

                # Additional stats section
                with st.expander("📊 Detailed Statistics", expanded=False):
                    stats_col1, stats_col2 = st.columns(2)

                    with stats_col1:
                        st.markdown("**Usage Statistics:**")
                        st.write(f"• Total weeks of data: {len(item_data)}")
                        st.write(f"• Average usage: {item_data['Usage'].mean():.2f}")
                        st.write(f"• Median usage: {item_data['Usage'].median():.2f}")
                        st.write(f"• Std deviation: {item_data['Usage'].std():.2f}")

                    with stats_col2:
                        st.markdown("**Peak Usage:**")
                        max_usage_idx = item_data['Usage'].idxmax()
                        max_usage_row = item_data.loc[max_usage_idx]
                        st.write(f"• Highest week: {max_usage_row['Usage']:.2f}")
                        st.write(f"• Date: {max_usage_row['Date'].strftime('%Y-%m-%d') if pd.notna(max_usage_row['Date']) else 'N/A'}")

                        min_usage_idx = item_data['Usage'].idxmin()
                        min_usage_row = item_data.loc[min_usage_idx]
                        st.write(f"• Lowest week: {min_usage_row['Usage']:.2f}")
                        st.write(f"• Date: {min_usage_row['Date'].strftime('%Y-%m-%d') if pd.notna(min_usage_row['Date']) else 'N/A'}")

                # Export option
                st.markdown("---")
                csv_export = item_data[['Date', 'Usage', 'End Inventory']].to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Item Data as CSV",
                    data=csv_export,
                    file_name=f"{selected_item.replace(' ', '_')}_trend_data.csv",
                    mime="text/csv"
                )
            else:
                st.warning(f"No data available for {selected_item} in the selected date range.")
        else:
            st.info("👆 Select an item to view its trend visualization.")

    # --- TAB 5: COGS ANALYSIS ---
    with tab_cogs:
        st.subheader("💰 Cost of Goods Sold (COGS) Analysis")
        st.markdown("Analyze your beverage costs, inventory value, and profitability metrics.")

        # Check if cost data is available
        items_with_cost = len(features_df[features_df['unit_cost'].notna()])
        items_total = len(features_df)

        if items_with_cost == 0:
            st.warning("⚠️ No cost data found in the uploaded files. Please ensure your BEVWEEKLY files include Unit Cost data in column 2.")
        else:
            st.info(f"📊 Cost data available for {items_with_cost} out of {items_total} items ({items_with_cost/items_total*100:.1f}%)")

            # Week selection dropdown
            all_weeks = dataset.get_all_cogs_summaries() if dataset else []
            if all_weeks:
                # Create week options with dates and status indicators
                week_options = {}
                for summary in all_weeks:
                    week_label = f"{summary.week_name} ({summary.week_date.strftime('%Y-%m-%d')})"
                    if summary.is_complete:
                        week_label += " ✅"
                    else:
                        week_label += " ⚠️ Incomplete"
                    week_options[week_label] = summary.week_name

                # Default to latest complete week
                latest_complete = dataset.get_latest_complete_cogs_summary()
                default_week_name = latest_complete.week_name if latest_complete else all_weeks[0].week_name
                default_label = next((label for label, name in week_options.items() if name == default_week_name), list(week_options.keys())[0])

                selected_week_label = st.selectbox(
                    "Select Week to View",
                    options=list(week_options.keys()),
                    index=list(week_options.keys()).index(default_label),
                    help="Choose which week's COGS data to display. ✅ indicates complete data (ending inventory filled in)."
                )

                selected_week = week_options[selected_week_label]
            else:
                selected_week = None

            # Get COGS summary (uses pre-calculated values from spreadsheet's "Weekly COGS" section)
            cogs_summary = get_cogs_summary(features_df, dataset, week_name=selected_week)

            # Section 1: Weekly COGS Summary
            st.markdown("### 📅 Weekly COGS Summary")

            # Show which week the data is from if available
            if 'week_name' in cogs_summary:
                week_status = ""
                if dataset and selected_week:
                    week_obj = dataset.get_cogs_summary_by_name(selected_week)
                    if week_obj and week_obj.is_complete:
                        week_status = " ✓ Complete"
                    else:
                        week_status = " ⚠️ Incomplete"
                st.caption(f"Showing data from: **{cogs_summary['week_name']}**{week_status}")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "Total COGS This Week",
                    f"${cogs_summary['total_weekly_cogs']:,.2f}",
                    help="Total cost of goods sold from the spreadsheet's Weekly COGS section"
                )

            with col2:
                st.metric(
                    "4-Week Average COGS",
                    f"${cogs_summary['total_avg_weekly_cogs_4wk']:,.2f}",
                    help="Average weekly COGS over last 4 weeks"
                )

            with col3:
                st.metric(
                    "Total Inventory Value",
                    f"${cogs_summary['total_inventory_value']:,.2f}",
                    help="Current value of inventory on hand"
                )

            with col4:
                st.metric(
                    "YTD COGS",
                    f"${cogs_summary['total_cogs_ytd']:,.2f}",
                    help="Year-to-date cost of goods sold"
                )

            st.markdown("---")

            # Section 2: COGS by Category (from spreadsheet's Weekly COGS section)
            st.markdown("### 📊 COGS by Category")

            # Show spreadsheet's pre-calculated COGS by category if available
            if 'liquor_cogs' in cogs_summary:
                cat_col1, cat_col2, cat_col3, cat_col4, cat_col5 = st.columns(5)
                with cat_col1:
                    st.metric("Liquor", f"${cogs_summary.get('liquor_cogs', 0) or 0:,.2f}")
                with cat_col2:
                    st.metric("Wine", f"${cogs_summary.get('wine_cogs', 0) or 0:,.2f}")
                with cat_col3:
                    st.metric("Draft Beer", f"${cogs_summary.get('draft_beer_cogs', 0) or 0:,.2f}")
                with cat_col4:
                    st.metric("Bottle Beer", f"${cogs_summary.get('bottle_beer_cogs', 0) or 0:,.2f}")
                with cat_col5:
                    st.metric("Juice", f"${cogs_summary.get('juice_cogs', 0) or 0:,.2f}")
                st.markdown("---")

            # Also show detailed breakdown by item categories
            cogs_by_cat = calculate_cogs_by_category(dataset, features_df)

            if not cogs_by_cat.empty:
                # Create bar chart
                fig_cat = px.bar(
                    cogs_by_cat.head(10),
                    x='category',
                    y='weekly_cogs',
                    title='Top 10 Categories by Weekly COGS',
                    labels={'category': 'Category', 'weekly_cogs': 'Weekly COGS ($)'},
                    color='weekly_cogs',
                    color_continuous_scale='Blues'
                )
                fig_cat.update_layout(showlegend=False, height=400)
                st.plotly_chart(fig_cat, use_container_width=True)

                # Show detailed table
                with st.expander("📋 Detailed Category Breakdown", expanded=False):
                    st.dataframe(
                        cogs_by_cat.style.format({
                            'weekly_cogs': '${:,.2f}',
                            'avg_weekly_cogs_4wk': '${:,.2f}',
                            'inventory_value': '${:,.2f}',
                            'cogs_ytd': '${:,.2f}'
                        }),
                        use_container_width=True,
                        hide_index=True
                    )

            st.markdown("---")

            # Section 3: COGS by Vendor
            st.markdown("### 🏢 COGS by Vendor")
            cogs_by_vendor = calculate_cogs_by_vendor(dataset, features_df)

            if not cogs_by_vendor.empty:
                # Create pie chart
                fig_vendor = px.pie(
                    cogs_by_vendor,
                    values='weekly_cogs',
                    names='vendor',
                    title='Weekly COGS Distribution by Vendor',
                    hole=0.4
                )
                fig_vendor.update_traces(textposition='inside', textinfo='percent+label')
                fig_vendor.update_layout(height=400)
                st.plotly_chart(fig_vendor, use_container_width=True)

                # Show detailed table
                with st.expander("📋 Detailed Vendor Breakdown", expanded=False):
                    st.dataframe(
                        cogs_by_vendor.style.format({
                            'weekly_cogs': '${:,.2f}',
                            'avg_weekly_cogs_4wk': '${:,.2f}',
                            'inventory_value': '${:,.2f}',
                            'cogs_ytd': '${:,.2f}'
                        }),
                        use_container_width=True,
                        hide_index=True
                    )

            st.markdown("---")

            # Section 4: Top Items by COGS
            st.markdown("### 🔝 Top 10 Highest COGS Items")

            # Filter items with cost data and sort by weekly_cogs
            items_with_cogs = features_df[features_df['weekly_cogs'].notna()].copy()
            items_with_cogs = items_with_cogs.sort_values('weekly_cogs', ascending=False).head(10)

            if not items_with_cogs.empty:
                # Calculate percentage of total
                total_cogs = cogs_summary['total_weekly_cogs']
                items_with_cogs['pct_of_total'] = (items_with_cogs['weekly_cogs'] / total_cogs * 100).round(1)

                # Display table
                display_cols = ['item_id', 'last_week_usage', 'unit_cost', 'weekly_cogs', 'pct_of_total']
                display_df = items_with_cogs[display_cols].copy()
                display_df.columns = ['Item', 'Usage', 'Unit Cost', 'COGS', '% of Total']

                st.dataframe(
                    display_df.style.format({
                        'Usage': '{:.2f}',
                        'Unit Cost': '${:.2f}',
                        'COGS': '${:.2f}',
                        '% of Total': '{:.1f}%'
                    }),
                    use_container_width=True,
                    hide_index=True
                )

            # Export option
            st.markdown("---")
            csv_export = features_df[['item_id', 'unit_cost', 'weekly_cogs', 'avg_weekly_cogs_4wk', 'inventory_value', 'cogs_ytd']].to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download COGS Data as CSV",
                data=csv_export,
                file_name="cogs_analysis.csv",
                mime="text/csv"
            )

    # --- TAB 6: POUR COST ANALYSIS ---
    with tab_pour_cost:
        st.subheader("📊 Pour Cost & Profitability Analysis")
        st.markdown("Analyze pour cost percentages, shrinkage, and variance between theoretical and actual usage.")

        # Get sales_mix_file from session_state (uploaded at top level)
        sales_mix_file = st.session_state.sales_mix_file

        if sales_mix_file is None:
            st.info("⬆️ Please upload a Sales Mix CSV file at the top of the page to calculate pour cost and variance analysis.")

        if sales_mix_file is not None:
            try:
                # Parse sales mix
                sales_df = parse_sales_mix_csv(sales_mix_file)

                # Week selector for COGS data
                st.markdown("---")
                st.markdown("### 📅 Select Week for COGS Analysis")

                # Get all available weeks
                all_weeks = dataset.get_all_cogs_summaries()

                if not all_weeks:
                    st.error("No COGS data available from bevweekly sheet. Please ensure the spreadsheet has the 'Weekly COGS' section filled in.")
                    st.stop()

                # Create week options for selectbox
                week_options = {}
                for summary in all_weeks:
                    week_label = f"{summary.week_name} ({summary.week_date.strftime('%Y-%m-%d')})"
                    if summary.is_complete:
                        week_label += " ✅"
                    else:
                        week_label += " ⚠️ Incomplete"
                    week_options[week_label] = summary.week_name

                # Default to latest complete week
                latest_complete = dataset.get_latest_complete_cogs_summary()
                default_week_name = latest_complete.week_name if latest_complete else all_weeks[0].week_name
                default_label = next((label for label, name in week_options.items() if name == default_week_name), list(week_options.keys())[0])

                # Week selector
                selected_week_label = st.selectbox(
                    "Select Week",
                    options=list(week_options.keys()),
                    index=list(week_options.keys()).index(default_label),
                    help="Choose which week's COGS data to use for analysis. ✅ indicates complete data (ending inventory filled in)."
                )

                selected_week_name = week_options[selected_week_label]

                st.markdown("---")

                # Calculate theoretical usage and revenue
                usage_results, unmatched, total_revenue = aggregate_all_usage(sales_df)

                # Calculate pour cost using ACTUAL COGS and SALES from bevweekly sheet for selected week
                pour_cost_results = calculate_pour_cost_actual(dataset, usage_results, week_name=selected_week_name)

                # Check if actual COGS and sales data are available
                if 'error' in pour_cost_results:
                    error_msg = pour_cost_results['error']
                    if 'Sales data not available' in error_msg:
                        st.warning(f"⚠️ {error_msg}")
                    else:
                        st.warning(f"⚠️ {error_msg}")
                    st.stop()

                # Also calculate theoretical COGS for variance analysis
                theoretical_cogs = calculate_theoretical_cogs(usage_results, dataset)

                # Section 1: Overall Pour Cost
                st.markdown("### 🎯 Overall Pour Cost")

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    pour_pct = pour_cost_results['overall_pour_cost_pct']
                    status_color = "🟢" if pour_pct <= 25 else "🟡" if pour_pct <= 30 else "🔴"
                    st.metric(
                        "Overall Pour Cost",
                        f"{pour_pct:.1f}%",
                        help="COGS / Revenue × 100"
                    )
                    st.markdown(f"{status_color} {'On Target' if pour_pct <= 25 else 'Warning' if pour_pct <= 30 else 'Critical'}")

                with col2:
                    st.metric(
                        "Total Revenue",
                        f"${pour_cost_results['total_revenue']:,.2f}",
                        help="Total sales from bevweekly sheet (column B - manager-entered)"
                    )

                with col3:
                    st.metric(
                        "Total COGS",
                        f"${pour_cost_results['total_cogs']:,.2f}",
                        help="Actual COGS from bevweekly sheet (BEG INV $ + PURCH $ - END INV $)"
                    )

                with col4:
                    st.metric(
                        "Gross Profit",
                        f"${pour_cost_results['gross_profit']:,.2f}",
                        help="Revenue - COGS"
                    )

                st.markdown("---")

                # Section 2: Pour Cost by Category
                st.markdown("### 📊 Pour Cost by Category")

                if pour_cost_results['pour_cost_by_category']:
                    # Convert to dataframe for display
                    pour_cat_data = []
                    for cat, data in pour_cost_results['pour_cost_by_category'].items():
                        status_emoji = "✅" if data['status'] == 'on_target' else "⚠️" if data['status'] == 'warning' else "🔴"
                        pour_cat_data.append({
                            'Category': cat,
                            'Revenue': data['revenue'],
                            'COGS': data['cogs'],
                            'Pour Cost %': data['pour_cost_pct'],
                            'Target %': data['target'],
                            'Status': f"{status_emoji} {data['status'].replace('_', ' ').title()}"
                        })

                    pour_cat_df = pd.DataFrame(pour_cat_data)
                    pour_cat_df = pour_cat_df.sort_values('Pour Cost %', ascending=False)

                    st.dataframe(
                        pour_cat_df.style.format({
                            'Revenue': '${:,.2f}',
                            'COGS': '${:,.2f}',
                            'Pour Cost %': '{:.1f}%',
                            'Target %': '{:.0f}%'
                        }),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("Pour cost by category data not available. Revenue breakdown by category is needed.")

                st.markdown("---")

                # Section 2.5: Pour Cost by Vendor
                st.markdown("### 🏢 Pour Cost by Vendor")

                # Calculate vendor breakdown
                vendor_cogs = {}
                vendor_revenue = {}

                for item_id, usage_data in usage_results.items():
                    item = dataset.get_item(item_id)
                    if not item:
                        continue

                    vendor = item.vendor
                    if vendor == "Unknown":
                        continue

                    # Get COGS for this item
                    item_cogs = theoretical_cogs['theoretical_cogs_by_item'].get(item_id, 0)

                    # Get revenue for this item
                    item_revenue = usage_data.get('revenue', 0)

                    # Aggregate by vendor
                    if vendor not in vendor_cogs:
                        vendor_cogs[vendor] = 0
                        vendor_revenue[vendor] = 0

                    vendor_cogs[vendor] += item_cogs
                    vendor_revenue[vendor] += item_revenue

                # Create vendor pour cost dataframe
                vendor_pour_data = []
                for vendor in vendor_cogs.keys():
                    cogs = vendor_cogs[vendor]
                    revenue = vendor_revenue[vendor]
                    pour_cost_pct = (cogs / revenue * 100) if revenue > 0 else 0

                    vendor_pour_data.append({
                        'Vendor': vendor,
                        'Revenue': revenue,
                        'COGS': cogs,
                        'Pour Cost %': pour_cost_pct
                    })

                if vendor_pour_data:
                    vendor_pour_df = pd.DataFrame(vendor_pour_data)
                    vendor_pour_df = vendor_pour_df.sort_values('Revenue', ascending=False)

                    st.dataframe(
                        vendor_pour_df.style.format({
                            'Revenue': '${:,.2f}',
                            'COGS': '${:,.2f}',
                            'Pour Cost %': '{:.1f}%'
                        }),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("Vendor pour cost data not available.")

                st.markdown("---")

                # Section 2.6: Individual Item Profitability
                st.markdown("### 💎 Individual Item Profitability")

                # Calculate item profitability using selected week's COGS
                profitability_df = calculate_item_profitability(usage_results, theoretical_cogs, dataset, week_name=selected_week_name)

                if not profitability_df.empty:
                    # Summary metrics with theoretical vs actual comparison
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        top_item = profitability_df.iloc[0]
                        st.metric(
                            "Top Profit Item",
                            top_item['item_id'][:20] + "..." if len(top_item['item_id']) > 20 else top_item['item_id'],
                            f"${top_item['actual_profit']:,.2f}",
                            help="Item contributing the most actual profit"
                        )

                    with col2:
                        avg_margin = profitability_df['actual_margin_pct'].mean()
                        st.metric(
                            "Avg Profit Margin",
                            f"{avg_margin:.1f}%",
                            help="Average actual profit margin across all items"
                        )

                    with col3:
                        theoretical_total = profitability_df['theoretical_profit'].sum()
                        actual_total = profitability_df['actual_profit'].sum()
                        variance = theoretical_total - actual_total
                        st.metric(
                            "Total Profit",
                            f"${actual_total:,.2f}",
                            delta=f"-${variance:,.2f}" if variance > 0 else f"+${abs(variance):,.2f}",
                            delta_color="inverse",
                            help=f"Actual profit vs theoretical ${theoretical_total:,.2f}. Variance shows profit loss due to waste/overpouring."
                        )

                    with col4:
                        poor_items = len(profitability_df[profitability_df['actual_margin_pct'] < 65])
                        st.metric(
                            "Low Margin Items",
                            poor_items,
                            help="Items with actual profit margin < 65%"
                        )

                    # Show top/bottom items
                    col_top, col_bottom = st.columns(2)

                    with col_top:
                        st.markdown("**Top 10 Most Profitable Items**")
                        top_10 = profitability_df.head(10).copy()
                        top_10['Status'] = top_10['status'].map({
                            'excellent': '🟢 Excellent',
                            'good': '🟡 Good',
                            'fair': '🟠 Fair',
                            'poor': '🔴 Poor'
                        })

                        display_cols = ['item_id', 'revenue', 'actual_cogs', 'actual_profit', 'actual_margin_pct', 'Status']
                        top_10_display = top_10[display_cols].copy()
                        top_10_display.columns = ['Item', 'Revenue', 'COGS', 'Profit', 'Margin %', 'Status']

                        st.dataframe(
                            top_10_display.style.format({
                                'Revenue': '${:,.2f}',
                                'COGS': '${:,.2f}',
                                'Profit': '${:,.2f}',
                                'Margin %': '{:.1f}%'
                            }),
                            use_container_width=True,
                            hide_index=True,
                            height=400
                        )

                    with col_bottom:
                        st.markdown("**Bottom 10 Least Profitable Items**")
                        bottom_10 = profitability_df.tail(10).copy()
                        bottom_10['Status'] = bottom_10['status'].map({
                            'excellent': '🟢 Excellent',
                            'good': '🟡 Good',
                            'fair': '🟠 Fair',
                            'poor': '🔴 Poor'
                        })

                        bottom_10_display = bottom_10[display_cols].copy()
                        bottom_10_display.columns = ['Item', 'Revenue', 'COGS', 'Profit', 'Margin %', 'Status']

                        st.dataframe(
                            bottom_10_display.style.format({
                                'Revenue': '${:,.2f}',
                                'COGS': '${:,.2f}',
                                'Profit': '${:,.2f}',
                                'Margin %': '{:.1f}%'
                            }),
                            use_container_width=True,
                            hide_index=True,
                            height=400
                        )

                    # Full profitability table in expander
                    with st.expander("📋 Full Item Profitability Report", expanded=False):
                        full_display = profitability_df.copy()
                        full_display['Status'] = full_display['status'].map({
                            'excellent': '🟢 Excellent',
                            'good': '🟡 Good',
                            'fair': '🟠 Fair',
                            'poor': '🔴 Poor'
                        })

                        # Show comprehensive view with theoretical vs actual comparison
                        full_display_cols = ['item_id', 'category', 'vendor', 'revenue', 'actual_cogs',
                                           'actual_profit', 'actual_margin_pct', 'theoretical_profit',
                                           'profit_variance', 'Status']
                        full_display = full_display[full_display_cols].copy()
                        full_display.columns = ['Item', 'Category', 'Vendor', 'Revenue', 'COGS',
                                               'Profit', 'Margin %', 'Theoretical Profit',
                                               'Variance', 'Status']

                        st.dataframe(
                            full_display.style.format({
                                'Revenue': '${:,.2f}',
                                'COGS': '${:,.2f}',
                                'Profit': '${:,.2f}',
                                'Margin %': '{:.1f}%',
                                'Theoretical Profit': '${:,.2f}',
                                'Variance': '${:,.2f}'
                            }),
                            use_container_width=True,
                            hide_index=True
                        )

                    # Export profitability data
                    csv_export_profit = profitability_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download Item Profitability as CSV",
                        data=csv_export_profit,
                        file_name="item_profitability.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("No profitability data available.")

                st.markdown("---")

                # Section 3: Variance Analysis
                st.markdown("### 📉 Variance Analysis (Theoretical vs Actual)")

                # Get actual usage from most recent week
                most_recent_week = dataset.records.sort_values('week_date', ascending=False)
                actual_usage_df = most_recent_week.groupby('item_id')['usage'].first().reset_index()

                # Calculate variance
                variance_df = calculate_variance_analysis(usage_results, actual_usage_df, dataset)

                if not variance_df.empty:
                    st.markdown("**All Item Variances (sorted by absolute dollar amount)**")

                    # Show all variances
                    top_variances = variance_df

                    # Add status icons
                    top_variances_display = top_variances.copy()
                    top_variances_display['Status'] = top_variances_display['severity'].map({
                        'normal': '✅ Normal',
                        'warning': '⚠️ Monitor',
                        'critical': '🔴 Investigate'
                    })

                    display_cols = ['item_id', 'category', 'theoretical', 'actual', 'variance_units', 'variance_dollars', 'variance_pct', 'Status']
                    display_df = top_variances_display[display_cols].copy()
                    display_df.columns = ['Item', 'Category', 'Theoretical', 'Actual', 'Variance (Units)', 'Variance ($)', 'Variance %', 'Status']

                    st.dataframe(
                        display_df.style.format({
                            'Theoretical': '{:.2f}',
                            'Actual': '{:.2f}',
                            'Variance (Units)': '{:.2f}',
                            'Variance ($)': '${:.2f}',
                            'Variance %': '{:.1f}%'
                        }),
                        use_container_width=True,
                        hide_index=True
                    )

                    # Shrinkage report
                    st.markdown("---")
                    st.markdown("### 🚨 Shrinkage Report (All Items with Loss)")

                    shrinkage_df = generate_shrinkage_report(variance_df, top_n=None)

                    if not shrinkage_df.empty:
                        shrinkage_display = shrinkage_df[['item_id', 'category', 'theoretical', 'actual', 'variance_units', 'variance_dollars', 'variance_pct']].copy()
                        shrinkage_display.columns = ['Item', 'Category', 'Theoretical', 'Actual', 'Over-Usage', 'Loss ($)', 'Loss %']

                        st.dataframe(
                            shrinkage_display.style.format({
                                'Theoretical': '{:.2f}',
                                'Actual': '{:.2f}',
                                'Over-Usage': '{:.2f}',
                                'Loss ($)': '${:.2f}',
                                'Loss %': '{:.1f}%'
                            }),
                            use_container_width=True,
                            hide_index=True
                        )

                        # Calculate total shrinkage
                        total_shrinkage = shrinkage_df['variance_dollars'].sum()
                        st.error(f"**Total Shrinkage (Loss): ${total_shrinkage:,.2f}**")
                    else:
                        st.success("✅ No significant shrinkage detected!")

                    # Export variance data
                    st.markdown("---")
                    csv_export = variance_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download Variance Analysis as CSV",
                        data=csv_export,
                        file_name="variance_analysis.csv",
                        mime="text/csv"
                    )

                # Show unmatched items
                if unmatched:
                    with st.expander(f"⚠️ Unmatched Items ({len(unmatched)})", expanded=False):
                        st.markdown("The following items from Sales Mix could not be matched to inventory items:")
                        for item in unmatched[:20]:  # Show first 20
                            st.text(f"• {item}")
                        if len(unmatched) > 20:
                            st.text(f"... and {len(unmatched) - 20} more")

            except Exception as e:
                st.error(f"Error processing Sales Mix file: {e}")
                import traceback
                st.code(traceback.format_exc())
        else:
            st.info("👆 Upload a Sales Mix CSV file to see pour cost analysis and variance reports.")

    # --- TAB 7: EXCESS INVENTORY ---
    with tab_excess_inventory:
        st.subheader("📦 Excess Inventory Analysis")
        st.markdown("Identify items with inventory levels exceeding suggested par levels based on average weekly usage.")

        st.markdown("---")

        # Settings
        st.markdown("### ⚙️ Calculation Settings")
        col1, col2 = st.columns(2)

        with col1:
            # Average usage method selector
            avg_method = st.selectbox(
                "Average Usage Calculation:",
                options=['4wk', '2wk', '10wk', 'ytd'],
                index=0,
                help="Select which averaging period to use for calculating weekly usage",
                key="excess_avg_method"
            )

            # Map to features_df column names
            avg_column_map = {
                '2wk': 'avg_2wk',
                '4wk': 'avg_4wk',
                '10wk': 'avg_10wk',
                'ytd': 'avg_ytd'
            }
            usage_column = avg_column_map[avg_method]

        with col2:
            # Target weeks override slider
            target_weeks_override = st.slider(
                "Target Weeks (Par Level):",
                min_value=1.0,
                max_value=8.0,
                value=0.0,
                step=0.5,
                help="Override default target weeks. Set to 0 to use category defaults (Draft Beer=2wk, Liquor=4wk, etc.)",
                key="excess_target_weeks"
            )

        st.markdown("---")

        # Initialize policy targets
        targets = OrderTargets()

        # Calculate excess inventory
        excess_items = []

        for _, row in features_df.iterrows():
            item_id = row['item_id']
            item = dataset.get_item(item_id)

            if not item:
                continue

            # Get average usage from selected column
            avg_weekly_usage = row.get(usage_column, 0)
            if pd.isna(avg_weekly_usage) or avg_weekly_usage <= 0:
                continue

            # Get current inventory
            on_hand = row['on_hand']
            unit_cost = item.unit_cost if item.unit_cost else 0

            # Get target weeks - use override if set, otherwise use category default
            if target_weeks_override > 0:
                target_weeks = target_weeks_override
            else:
                target_weeks = targets.get_target_weeks(item_id, item.category)

            # Calculate suggested par level
            suggested_par = target_weeks * avg_weekly_usage

            # Calculate excess
            excess_units = max(0, on_hand - suggested_par)
            excess_value = excess_units * unit_cost

            # Only include items with significant excess (> 0.5 units or > $5)
            if excess_units > 0.5 or excess_value > 5:
                starting_inv_value = on_hand * unit_cost

                excess_items.append({
                    'Product': item_id,
                    'Category': item.category,
                    'Vendor': item.vendor if item.vendor else 'Unknown',
                    'Price': unit_cost,
                    'Starting Inv Units': round(on_hand, 1),
                    'Starting Inv Value': round(starting_inv_value, 2),
                    'Avg Weekly': round(avg_weekly_usage, 1),
                    'Target Weeks': target_weeks,
                    'Suggested': round(suggested_par, 1),
                    'Excess Inv Units': round(excess_units, 1),
                    'Excess Inv Value': round(excess_value, 2)
                })

        # Create DataFrame and sort by excess value (highest first)
        if excess_items:
            excess_df = pd.DataFrame(excess_items)
            excess_df = excess_df.sort_values('Excess Inv Value', ascending=False)

            # Filters - positioned BEFORE summary so summary updates with filters
            st.markdown("### 🔍 Filters")
            col1, col2 = st.columns(2)

            with col1:
                all_categories = ['All'] + sorted(excess_df['Category'].unique().tolist())
                selected_category = st.selectbox(
                    "Category:",
                    options=all_categories,
                    key="excess_category_filter"
                )

            with col2:
                all_vendors = ['All'] + sorted(excess_df['Vendor'].unique().tolist())
                selected_vendor = st.selectbox(
                    "Vendor:",
                    options=all_vendors,
                    key="excess_vendor_filter"
                )

            # Filter dataframe by category and vendor
            filtered_df = excess_df.copy()

            if selected_category != 'All':
                filtered_df = filtered_df[filtered_df['Category'] == selected_category]

            if selected_vendor != 'All':
                filtered_df = filtered_df[filtered_df['Vendor'] == selected_vendor]

            st.markdown("---")

            # Calculate totals AFTER filtering - so summary updates with filters
            total_items_with_excess = len(filtered_df)
            total_excess_value = filtered_df['Excess Inv Value'].sum()
            total_inventory_value = filtered_df['Starting Inv Value'].sum()
            excess_percentage = (total_excess_value / total_inventory_value * 100) if total_inventory_value > 0 else 0

            # Prominent Total Excess Value Display (updates with filters)
            st.markdown("### 💰 Total Excess Inventory Value")
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "Items with Excess",
                    f"{total_items_with_excess:,}",
                    help="Number of items with inventory above suggested par level (filtered)"
                )

            with col2:
                st.metric(
                    "🔴 Total Excess Value",
                    f"${total_excess_value:,.2f}",
                    help="Total dollar value of excess inventory (filtered)"
                )

            with col3:
                st.metric(
                    "Total Inventory Value",
                    f"${total_inventory_value:,.2f}",
                    help="Total value of all items shown (filtered)"
                )

            with col4:
                st.metric(
                    "Excess %",
                    f"{excess_percentage:.1f}%",
                    help="Percentage of inventory that is excess (filtered)"
                )

            st.markdown("---")

            # Display settings
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(f"### 📦 Top Items with Excess Inventory ({len(filtered_df)} items)")
            with col2:
                show_all = st.checkbox("Show all items", value=False, key="show_all_excess")

            # Limit to top 20 unless show_all is checked
            display_df = filtered_df if show_all else filtered_df.head(20)

            # Format and display table
            st.dataframe(
                display_df.style.format({
                    'Price': '${:.2f}',
                    'Starting Inv Units': '{:.1f}',
                    'Starting Inv Value': '${:.2f}',
                    'Avg Weekly': '{:.1f}',
                    'Target Weeks': '{:.1f}',
                    'Suggested': '{:.1f}',
                    'Excess Inv Units': '{:.1f}',
                    'Excess Inv Value': '${:.2f}'
                }),
                use_container_width=True,
                hide_index=True,
                height=600
            )

            # Export to CSV
            st.markdown("---")
            target_label = f"{target_weeks_override:.1f}wk" if target_weeks_override > 0 else "default"
            csv_export = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Excess Inventory Report as CSV",
                data=csv_export,
                file_name=f"excess_inventory_{avg_method}_target_{target_label}.csv",
                mime="text/csv"
            )

            # Recommendations
            st.markdown("---")
            st.markdown("### 💡 Recommendations")
            target_desc = f"**{target_weeks_override:.1f} weeks**" if target_weeks_override > 0 else "**category defaults**"
            st.info(f"""
            **Current Settings:**
            - Average Usage: **{avg_method}**
            - Target Weeks: {target_desc}

            **Action Items:**
            1. **Reduce Orders**: Consider reducing or skipping orders for items with high excess inventory
            2. **Run Promotions**: Feature high-excess items in specials or happy hour to move inventory
            3. **Adjust Par Levels**: Use the Target Weeks slider to see how different par levels affect excess
            4. **Check for Changes**: Items may have had a recent drop in sales - investigate why
            5. **Vendor Analysis**: Filter by vendor to identify which suppliers contribute most to excess inventory

            **Tips:**
            - Try different averaging methods (2wk, 4wk, 10wk) to see how responsive vs stable averages affect excess calculations
            - Adjust Target Weeks slider to simulate tighter (lower) or looser (higher) par levels
            - Filter by vendor to focus on specific supplier relationships
            - Export filtered data to share with purchasing team
            """)
            
        else:
            st.success("✅ No excess inventory detected! All items are at or below suggested par levels.")
            st.info(f"Try adjusting the averaging method or Target Weeks slider to see how different settings affect excess inventory calculations.")
