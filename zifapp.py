import streamlit as st
import pandas as pd
from datetime import datetime
from utils import parse_sales_mix_csv, aggregate_all_usage
from statsmodels.tsa.holtwinters import SimpleExpSmoothing
import re
import math
import plotly.express as px

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

# --- Main App UI ---
uploaded_files = st.file_uploader(
    "Upload your BEVWEEKLY Excel Files (you can select multiple years)",
    type="xlsx",
    accept_multiple_files=True,
    help="Hold Ctrl/Cmd to select multiple files, or drag & drop multiple files. Upload multiple years (e.g., 2026, 2025, 2024) to see historical trends."
)

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

    try:
        summary_df, vendor_map, category_map, full_df = load_and_process_data(uploaded_files, smoothing_level, trend_threshold)

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

    tab_summary, tab_ordering_worksheet, tab_sales_mix, tab_trends = st.tabs(["📊 Summary", "🧪 Ordering Worksheet", "Sales Mix Analysis", "📈 Item Trends"])

    # --- TAB 1: SUMMARY ---
    with tab_summary:
        st.subheader("Usage Summary")
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
        Upload your Sales Mix CSV from GEMpos to calculate theoretical usage based on what was sold.
        Compare against your actual inventory usage to identify variances (waste, over-pouring, theft, etc.)
        """)
        
        sales_mix_file = st.file_uploader("Upload Sales Mix CSV", type="csv", key="sales_mix_upload")
        
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
                    all_usage, unmatched_items = aggregate_all_usage(sales_df)
                    
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
