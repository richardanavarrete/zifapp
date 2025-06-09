import streamlit as st
import pandas as pd
from datetime import datetime
import math
from io import BytesIO
import json
import os

# --- Page Configuration (MUST BE THE FIRST STREAMLIT COMMAND) ---
st.set_page_config(page_title="Bev Usage Analyzer", layout="wide")
st.title("🍺 Bev Usage Analyzer")

# --- Constants ---
LAYOUT_FILE = "inventory_layout.json"
MAPPINGS_FILE = "vendor_map.json" # Updated to use the new filename

# --- Helper function to load mappings ---
def load_mappings():
    """Loads the vendor mappings from the external JSON file."""
    try:
        with open(MAPPINGS_FILE, 'r') as f:
            mappings = json.load(f)
            vendor_map = mappings.get("vendor_map", {})
            # Ensure all items in the map are stripped of whitespace
            for vendor, items in vendor_map.items():
                vendor_map[vendor] = [str(item).strip() for item in items]
            return vendor_map
    except (FileNotFoundError, json.JSONDecodeError):
        st.error(f"Error: The '{MAPPINGS_FILE}' was not found or is not a valid JSON file. Please make sure it's in the same directory as the script.")
        return None


# --- Caching the data processing ---
@st.cache_data
def load_and_process_data(uploaded_file):
    """
    Reads the uploaded Excel file, processes all data, and calculates summary metrics.
    """
    vendor_map = load_mappings()
    if vendor_map is None:
        return None, None, None # Stop processing if mappings failed to load

    xls = pd.ExcelFile(uploaded_file)
    sheet_names = xls.sheet_names

    # Get the original intended sort order from the first sheet
    try:
        original_order_df = xls.parse(sheet_names[0], skiprows=4)
        original_order = original_order_df.iloc[:, 0].dropna().astype(str).tolist()
    except Exception as e:
        st.error(f"Could not read the item order from the first sheet. Error: {e}")
        return None, None, None

    # Compile data from all sheets
    compiled_data = []
    for sheet in sheet_names:
        try:
            date_value = xls.parse(sheet, header=None).iloc[1, 0]
            df = xls.parse(sheet, skiprows=4)
            df = df.rename(columns={
                df.columns[0]: 'Item', df.columns[9]: 'Usage', df.columns[7]: 'End Inventory'
            })
            df = df[['Item', 'Usage', 'End Inventory']]
            df['Week'] = sheet
            df['Date'] = pd.to_datetime(date_value) if isinstance(date_value, datetime) else pd.NaT
            compiled_data.append(df)
        except Exception as e:
            st.warning(f"Could not process sheet: '{sheet}'. It might have a different format. Error: {e}")
            continue

    if not compiled_data:
        st.error("No data could be compiled from the uploaded file. Please check the file format.")
        return None, None, None

    # Combine and clean the data
    full_df = pd.concat(compiled_data, ignore_index=True)
    full_df = full_df.dropna(subset=['Item', 'Usage'])
    full_df['Item'] = full_df['Item'].astype(str).str.strip()
    full_df = full_df[~full_df['Item'].str.upper().str.startswith('TOTAL')]
    full_df['Usage'] = pd.to_numeric(full_df['Usage'], errors='coerce')
    full_df['End Inventory'] = pd.to_numeric(full_df['End Inventory'], errors='coerce')
    full_df = full_df.dropna(subset=['Usage', 'End Inventory'])
    full_df = full_df.sort_values(by=['Item', 'Date'])

    def compute_metrics(group):
        usage = group['Usage']
        inventory = group['End Inventory']
        dates = group['Date']

        last_10, last_4 = usage.tail(10), usage.tail(4)
        ytd_avg = group[dates.dt.year == datetime.now().year]['Usage'].mean() if pd.api.types.is_datetime64_any_dtype(dates) else None

        def safe_div(n, d):
            if pd.notna(d) and d > 0: return round(n / d, 2)
            return None

        avg_of_highest_4 = usage.nlargest(4).mean() if not usage.empty else None
        non_zero_usage = usage[usage > 0]
        avg_of_lowest_4_non_zero = non_zero_usage.nsmallest(4).mean() if not non_zero_usage.empty else None

        return pd.Series({
            'On Hand': round(inventory.iloc[-1], 2),
            'Year-to-Date Average': round(ytd_avg, 2) if pd.notna(ytd_avg) else None,
            '10-Week Average': round(last_10.mean(), 2) if not last_10.empty else None,
            '4-Week Average': round(last_4.mean(), 2) if not last_4.empty else None,
            'All-Time High': round(usage.max(), 2),
            'Lowest 4 Average (non-zero)': round(avg_of_lowest_4_non_zero, 2) if pd.notna(avg_of_lowest_4_non_zero) else None,
            'Highest 4 Average': round(avg_of_highest_4, 2) if pd.notna(avg_of_highest_4) else None,
            'Weeks Remaining (YTD)': safe_div(inventory.iloc[-1], ytd_avg),
            'Weeks Remaining (10 Wk)': safe_div(inventory.iloc[-1], last_10.mean()),
            'Weeks Remaining (4 Wk)': safe_div(inventory.iloc[-1], last_4.mean()),
            'Weeks Remaining (ATH)': safe_div(inventory.iloc[-1], usage.max()),
            'Weeks Remaining (Lowest 4)': safe_div(inventory.iloc[-1], avg_of_lowest_4_non_zero),
            'Weeks Remaining (Highest 4)': safe_div(inventory.iloc[-1], avg_of_highest_4)
        })

    summary_df = full_df.groupby('Item').apply(compute_metrics).reset_index()

    # Apply original sort order
    summary_df['Item'] = summary_df['Item'].astype(str)
    original_order_cleaned = [str(item).strip() for item in original_order]
    summary_df['ItemOrder'] = summary_df['Item'].apply(lambda x: original_order_cleaned.index(x) if x in original_order_cleaned else float('inf'))
    summary_df = summary_df.sort_values(by='ItemOrder').drop(columns='ItemOrder')

    # --- DYNAMIC CATEGORY MAPPING ---
    category_map = {}
    for item in summary_df['Item']:
        upper_item = item.upper().strip()
        cat = "Other" # Default category
        if "WELL" in upper_item: cat = "Well"
        elif "WHISKEY" in upper_item: cat = "Whiskey"
        elif "VODKA" in upper_item: cat = "Vodka"
        elif "GIN" in upper_item: cat = "Gin"
        elif "TEQUILA" in upper_item: cat = "Tequila"
        elif "RUM" in upper_item: cat = "Rum"
        elif "SCOTCH" in upper_item: cat = "Scotch"
        elif "LIQ" in upper_item and "SCHNAPPS" not in upper_item: cat = "Liqueur"
        elif "SCHNAPPS" in upper_item: cat = "Cordials"
        elif "WINE" in upper_item: cat = "Wine"
        elif "BEER DFT" in upper_item: cat = "Draft Beer"
        elif "BEER BTL" in upper_item: cat = "Bottled Beer"
        elif "JUICE" in upper_item: cat = "Juice"
        elif "BAR CONS" in upper_item: cat = "Bar Consumables"

        if cat not in category_map:
            category_map[cat] = []
        category_map[cat].append(item)

    return summary_df, vendor_map, category_map

# --- Main App UI ---
uploaded_file = st.file_uploader("Upload your BEVWEEKLY Excel File", type="xlsx")

if uploaded_file:
    app_mode = st.radio(
        "Select a mode:",
        ["Analyze Past Usage & Plan Orders", "Configure Inventory Layout", "Take New Inventory"],
        horizontal=True,
    )
    st.markdown("---")

    # Load data once and store in session state to pass between modes
    if 'data_loaded' not in st.session_state:
        # Now load_and_process_data will also load the vendor_map from the JSON file
        st.session_state.summary_df, st.session_state.vendor_map, st.session_state.category_map = load_and_process_data(uploaded_file)
        if st.session_state.summary_df is not None:
            st.session_state.data_loaded = True
        else:
            # Error messages are now handled inside the loading functions
            st.stop()

    summary_df = st.session_state.summary_df
    vendor_map = st.session_state.vendor_map
    category_map = st.session_state.category_map

    # --- Mode 1: Analysis and Ordering ---
    if app_mode == "Analyze Past Usage & Plan Orders":
        tab_summary, tab_ordering_worksheet = st.tabs(["📊 Summary", "🧪 Ordering Worksheet"])

        with tab_summary:
            st.subheader("Usage Summary")
            filter_type = st.radio("Filter By:", ["Vendor", "Category"], horizontal=True, key="summary_filter_type")

            display_df = summary_df
            if filter_type == "Vendor":
                vendor_options = ["All Vendors"] + list(vendor_map.keys())
                selected_vendor = st.selectbox("Select Vendor", options=vendor_options, key="summary_vendor_select")
                if selected_vendor != "All Vendors":
                    display_df = summary_df[summary_df['Item'].isin(vendor_map.get(selected_vendor, []))]
            elif filter_type == "Category":
                category_options = ["All Categories"] + list(category_map.keys())
                selected_category = st.selectbox("Select Category", options=category_options, key="summary_category_select")
                if selected_category != "All Categories":
                    display_df = summary_df[summary_df['Item'].isin(category_map.get(selected_category, []))]

            threshold = st.slider("Highlight if weeks remaining is below:", min_value=0.2, max_value=10.0, value=2.0, step=0.1)

            def highlight_weeks_remaining(val, threshold=2.0):
                if pd.notna(val) and isinstance(val, (int, float)) and val < threshold: return 'background-color: #ff4b4b'
                return ''

            format_dict = {col: '{:,.2f}' for col in display_df.select_dtypes(include=['float64', 'float32']).columns}
            styled_df = display_df.style.format(format_dict, na_rep="-").apply(
                highlight_weeks_remaining, threshold=threshold,
                subset=['Weeks Remaining (YTD)', 'Weeks Remaining (10 Wk)', 'Weeks Remaining (4 Wk)', 'Weeks Remaining (ATH)', 'Weeks Remaining (Lowest 4)', 'Weeks Remaining (Highest 4)'],
                axis=None # Apply element-wise
            )
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            csv = display_df.to_csv(index=False).encode('utf-8')
            st.download_button("Download Summary CSV", data=csv, file_name="beverage_summary.csv")

        with tab_ordering_worksheet:
            st.subheader("🧪 Ordering Worksheet: Inventory Planning")

            # --- SETUP CONTROLS ---
            c1, c2, c3 = st.columns(3)
            mode = c1.selectbox("Select View Mode:", ["By Vendor", "By Category"], key="worksheet_mode")
            usage_option = c3.selectbox(
                "Select Usage Average for Calculation:",
                options=['4-Week Average', '10-Week Average', 'Year-to-Date Average', 'Lowest 4 Average (non-zero)', 'Highest 4 Average'],
                index=0, key="usage_radio"
            )

            items_to_display = []
            filter_selection = None
            if mode == "By Vendor":
                vendor = c2.selectbox("Select Vendor", list(vendor_map.keys()), key="vendor_select")
                items_to_display = vendor_map.get(vendor, [])
                filter_selection = vendor
            else:
                selected_category = c2.selectbox("Select Category", list(category_map.keys()), key="category_select")
                items_to_display = category_map.get(selected_category, [])
                filter_selection = selected_category

            # --- SESSION STATE MANAGEMENT FOR THE DATA EDITOR ---
            worksheet_state_key = f"worksheet_df_{mode}_{filter_selection}_{usage_option}"

            if 'current_worksheet_key' not in st.session_state or st.session_state.current_worksheet_key != worksheet_state_key:
                filtered_df = summary_df[summary_df['Item'].isin(items_to_display)]
                editor_df_data = {
                    'Item': filtered_df['Item'], 'On Hand': filtered_df['On Hand'],
                    'Selected Avg': filtered_df[usage_option], 'Order Qty (Bottles)': 0, 'Target Weeks of Supply': 4.0
                }
                worksheet_df = pd.DataFrame(editor_df_data)
                worksheet_df['Selected Avg'] = pd.to_numeric(worksheet_df['Selected Avg'], errors='coerce').fillna(0)
                worksheet_df['Order Qty (Bottles)'] = worksheet_df.apply(
                    lambda r: max(0, int(math.ceil((r['Target Weeks of Supply'] * r['Selected Avg']) - r['On Hand']))) if r['Selected Avg'] > 0 else 0,
                    axis=1
                )
                def temp_safe_div(n, d):
                    return round(n / d, 1) if d and pd.notna(d) and d > 0 else 0.0
                worksheet_df['Current Wks Left'] = worksheet_df.apply(lambda row: temp_safe_div(row['On Hand'], row['Selected Avg']), axis=1)

                st.session_state[worksheet_state_key] = worksheet_df[['Item', 'On Hand', 'Current Wks Left', 'Selected Avg', 'Order Qty (Bottles)', 'Target Weeks of Supply']]
                st.session_state.current_worksheet_key = worksheet_state_key
                st.session_state.last_edited_column = None

            # --- BULK EDIT CONTROLS ---
            st.markdown("---")
            col1, col2 = st.columns([3, 1])
            with col1:
                bulk_week_target = st.slider(
                    "Set a target for all items below:",
                    min_value=0.0, max_value=12.0, value=4.0, step=0.5, key="bulk_week_slider"
                )
            with col2:
                st.write("") # Spacer
                if st.button("Apply Target to All", use_container_width=True):
                    df_to_update = st.session_state[worksheet_state_key].copy()
                    df_to_update['Target Weeks of Supply'] = bulk_week_target
                    df_to_update['Order Qty (Bottles)'] = df_to_update.apply(
                        lambda r: max(0, int(math.ceil((r['Target Weeks of Supply'] * r['Selected Avg']) - r['On Hand']))) if r['Selected Avg'] > 0 else 0,
                        axis=1
                    )
                    st.session_state[worksheet_state_key] = df_to_update
                    st.rerun()

            # --- DATA EDITOR ---
            edited_df = st.data_editor(
                st.session_state[worksheet_state_key], hide_index=True, use_container_width=True, key="order_editor",
                column_config={
                    "Item": st.column_config.TextColumn(disabled=True, width="large"),
                    "On Hand": st.column_config.NumberColumn(format="%.2f", disabled=True),
                    "Current Wks Left": st.column_config.NumberColumn(format="%.1f", help="Current inventory in terms of weeks of supply.", disabled=True),
                    "Selected Avg": st.column_config.NumberColumn(f"Avg Usage", format="%.2f", disabled=True),
                    "Order Qty (Bottles)": st.column_config.NumberColumn(min_value=0, step=1, format="%d"),
                    "Target Weeks of Supply": st.column_config.NumberColumn(help="Enter a target total weeks of supply to calculate bottles needed.", min_value=0.0, step=0.5, format="%.1f")
                }
            )

            # --- CALCULATION LOGIC ON EDIT ---
            if not edited_df.equals(st.session_state[worksheet_state_key]):
                original_df = st.session_state[worksheet_state_key]
                if not edited_df['Order Qty (Bottles)'].equals(original_df['Order Qty (Bottles)']):
                    st.session_state.last_edited_column = 'Bottles'
                elif not edited_df['Target Weeks of Supply'].equals(original_df['Target Weeks of Supply']):
                    st.session_state.last_edited_column = 'Weeks'

                new_df = edited_df.copy()
                if st.session_state.last_edited_column == 'Bottles':
                    new_df['Target Weeks of Supply'] = new_df.apply(lambda r: (r['On Hand'] + r['Order Qty (Bottles)']) / r['Selected Avg'] if r['Selected Avg'] > 0 else 0, axis=1)
                elif st.session_state.last_edited_column == 'Weeks':
                    new_df['Order Qty (Bottles)'] = new_df.apply(
                        lambda r: max(0, int(math.ceil((r['Target Weeks of Supply'] * r['Selected Avg']) - r['On Hand']))) if r['Selected Avg'] > 0 else 0,
                        axis=1
                    )

                st.session_state[worksheet_state_key] = new_df
                st.rerun()

            # --- FINAL ORDER SUMMARY ---
            st.markdown("---")
            if st.button("Generate Final Order Summary"):
                order_df = st.session_state[worksheet_state_key]
                items_to_order = order_df[order_df['Order Qty (Bottles)'] > 0]
                if not items_to_order.empty:
                    st.subheader("Final Order Summary")
                    st.dataframe(items_to_order[['Item', 'On Hand', 'Order Qty (Bottles)', 'Target Weeks of Supply']], use_container_width=True, hide_index=True)
                    csv_order = items_to_order.to_csv(index=False).encode('utf-8')
                    st.download_button("Download Final Order CSV", data=csv_order, file_name=f"order_{filter_selection}.csv")
                else:
                    st.warning("No items have been marked for order.")


    # --- Mode 2: Configure Layout ---
    elif app_mode == "Configure Inventory Layout":
        st.subheader("⚙️ Configure Inventory Count Layout")
        st.markdown("Here you can define physical locations and the order of items within them to make inventory counting faster.")

        if 'inventory_layout' not in st.session_state:
            try:
                with open(LAYOUT_FILE, 'r') as f:
                    st.session_state.inventory_layout = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                st.session_state.inventory_layout = {}

        st.markdown("##### 1. Add or Remove Locations")
        new_location = st.text_input("New Location Name:")
        if st.button("Add Location"):
            if new_location and new_location not in st.session_state.inventory_layout:
                st.session_state.inventory_layout[new_location] = []
                st.rerun()

        if st.session_state.inventory_layout:
            locations = list(st.session_state.inventory_layout.keys())
            location_to_remove = st.selectbox("Select a location to remove (optional):", [""] + locations, key="remove_loc_select")
            if st.button("Remove Selected Location", type="primary"):
                if location_to_remove:
                    del st.session_state.inventory_layout[location_to_remove]
                    st.rerun()

        st.markdown("---")
        st.markdown("##### 2. Assign Items and Set Count Order")
        if not st.session_state.inventory_layout:
            st.warning("Please add at least one location to begin.")
        else:
            all_items_in_file = summary_df['Item'].tolist()
            assigned_items = [item for sublist in st.session_state.inventory_layout.values() for item in sublist]

            location_tabs = st.tabs(list(st.session_state.inventory_layout.keys()))
            for i, tab in enumerate(location_tabs):
                location_name = list(st.session_state.inventory_layout.keys())[i]
                with tab:
                    st.markdown(f"#### Edit Layout for: **{location_name}**")

                    available_items = sorted([item for item in all_items_in_file if item not in assigned_items])
                    items_to_add = st.multiselect("Select items to add to this location:", options=available_items, key=f"add_{location_name}")
                    if st.button("Add Selected Items", key=f"add_btn_{location_name}"):
                        st.session_state.inventory_layout[location_name].extend(items_to_add)
                        st.rerun()

                    st.markdown("**Items in this location (Drag to Reorder):**")
                    if st.session_state.inventory_layout[location_name]:
                        items_df = pd.DataFrame({'Item Name': st.session_state.inventory_layout[location_name]})
                        edited_items_df = st.data_editor(
                            items_df,
                            key=f"editor_{location_name}",
                            hide_index=True,
                            use_container_width=True,
                            num_rows="dynamic"
                        )
                        if edited_items_df['Item Name'].tolist() != st.session_state.inventory_layout[location_name]:
                            st.session_state.inventory_layout[location_name] = edited_items_df['Item Name'].tolist()
                            st.rerun()

        st.markdown("---")
        if st.button("💾 Save Layout to File", type="primary", use_container_width=True):
            with open(LAYOUT_FILE, 'w') as f:
                json.dump(st.session_state.inventory_layout, f, indent=4)
            st.success("Inventory layout saved successfully!")

    # --- Mode 3: Take New Inventory ---
    elif app_mode == "Take New Inventory":
        st.subheader("📝 Take New Inventory")

        # --- Load Layout and Initialize State ---
        if 'inventory_layout' not in st.session_state:
            try:
                with open(LAYOUT_FILE, 'r') as f:
                    st.session_state.inventory_layout = json.load(f)
            except FileNotFoundError:
                st.session_state.inventory_layout = {}

        if not st.session_state.inventory_layout:
            st.warning("You must first set up your inventory locations. Go to the 'Configure Inventory Layout' mode.")
            st.stop()

        xls = pd.ExcelFile(uploaded_file)
        sheet_names = xls.sheet_names
        all_items = sorted(list(set(pd.read_excel(xls, sheet_name=sheet_names[0], skiprows=4).iloc[:, 0].dropna().astype(str).str.strip().tolist())))
        all_items = [item for item in all_items if not item.upper().startswith('TOTAL')]

        selected_week = st.selectbox("Which week are you taking inventory for?", options=xls.sheet_names, key="inv_week_select")

        # Initialize session state keys for inventory taking
        if 'master_inventory_counts' not in st.session_state or st.session_state.get('current_inventory_week') != selected_week:
            st.session_state.master_inventory_counts = {}
            st.session_state.current_inventory_week = selected_week
            st.session_state.current_location_index = 0
            st.session_state.current_item_index = 0
            st.session_state.calculator_value = 0.0
            st.info(f"Starting new inventory for week: **{selected_week}**. All previous counts cleared.")

        if 'calculator_value' not in st.session_state: st.session_state.calculator_value = 0.0
        if 'current_location_index' not in st.session_state: st.session_state.current_location_index = 0
        if 'current_item_index' not in st.session_state: st.session_state.current_item_index = 0

        # --- Location and Item Navigation ---
        location_names = list(st.session_state.inventory_layout.keys())
        st.session_state.current_location_index = st.selectbox("Location:", options=range(len(location_names)), format_func=lambda x: location_names[x], key="location_selector")

        selected_location_name = location_names[st.session_state.current_location_index]
        items_in_location = st.session_state.inventory_layout.get(selected_location_name, [])

        st.markdown("---")

        if items_in_location:
            # Ensure index is within bounds after a location change
            if st.session_state.current_item_index >= len(items_in_location):
                st.session_state.current_item_index = 0

            # Set the current item based on the index in the guided path
            st.session_state.current_inventory_item = items_in_location[st.session_state.current_item_index]

            col1, col2, col3 = st.columns([1,2,1])
            with col1:
                if st.button("◀ Previous Item", use_container_width=True):
                    if st.session_state.current_item_index > 0:
                        st.session_state.current_item_index -= 1
                        st.rerun()
            with col3:
                if st.button("Next Item ▶", use_container_width=True):
                     if st.session_state.current_item_index < len(items_in_location) - 1:
                        st.session_state.current_item_index += 1
                        st.rerun()
            with col2:
                st.markdown(f"<h4 style='text-align: center; color: orange;'>Counting: {st.session_state.current_inventory_item}</h4>", unsafe_allow_html=True)
        else:
            st.warning(f"No items have been assigned to the '{selected_location_name}' location. Please configure your layout.")

        item_to_count = st.selectbox(
            "Or, search for any item to count:",
            options=all_items,
            index=all_items.index(st.session_state.current_inventory_item) if st.session_state.current_inventory_item in all_items else 0
        )

        st.markdown(f"#### Log Partial Counts for: **{item_to_count}**")

        # Initialize partial counts for the selected item if it doesn't exist
        if item_to_count not in st.session_state.master_inventory_counts:
            st.session_state.master_inventory_counts[item_to_count] = []

        st.markdown("---")
        # --- "Abacus" Calculator for Adding New Partial Counts ---
        st.markdown("###### Add New Partial Count:")
        if 'calculator_value' not in st.session_state:
            st.session_state.calculator_value = 0.0

        def reset_calculator():
            st.session_state.calculator_value = 0.0

        def add_to_calculator(amount):
            st.session_state.calculator_value += amount

        def log_count(item):
            count_to_log = st.session_state.calculator_value
            if count_to_log > 0:
                # Find the first empty (0.0) slot to log the new count
                current_counts = st.session_state.master_inventory_counts.get(item, [0.0]*6)
                try:
                    first_empty_slot_index = current_counts.index(0.0)
                    current_counts[first_empty_slot_index] = count_to_log
                    st.session_state.master_inventory_counts[item] = current_counts
                    # Advance to next item if possible
                    location_names = list(st.session_state.inventory_layout.keys())
                    selected_location_name = location_names[st.session_state.current_location_index]
                    items_in_location = st.session_state.inventory_layout.get(selected_location_name, [])
                    if st.session_state.current_item_index < len(items_in_location) - 1:
                        st.session_state.current_item_index += 1
                    st.session_state.calculator_value = 0.0
                    st.rerun()
                except ValueError:
                    st.warning("All 6 slots are full for this item. Please clear a slot to add a new count.")
            else:
                st.session_state.calculator_value = 0.0

        st.number_input("Build count here:", min_value=0.0, step=1.0, key="calculator_value")

        q_col1, q_col2, q_col3, q_col4 = st.columns(4)
        q_col1.button("+0.1", on_click=add_to_calculator, args=(0.1,), use_container_width=True)
        q_col1.button("+0.3", on_click=add_to_calculator, args=(0.3,), use_container_width=True)
        q_col1.button("+0.5", on_click=add_to_calculator, args=(0.5,), use_container_width=True)
        q_col2.button("+1", on_click=add_to_calculator, args=(1.0,), use_container_width=True)
        q_col2.button("+3", on_click=add_to_calculator, args=(3.0,), use_container_width=True)
        q_col2.button("+5", on_click=add_to_calculator, args=(5.0,), use_container_width=True)
        q_col3.button("+6", on_click=add_to_calculator, args=(6.0,), use_container_width=True)
        q_col3.button("+8", on_click=add_to_calculator, args=(8.0,), use_container_width=True)
        q_col3.button("+10", on_click=add_to_calculator, args=(10.0,), use_container_width=True)
        q_col4.button("+12", on_click=add_to_calculator, args=(12.0,), use_container_width=True)
        q_col4.button("+24", on_click=add_to_calculator, args=(24.0,), use_container_width=True)

        q_col4.button("Clear", on_click=reset_calculator, use_container_width=True)

        st.button("Log Partial Count to Next Available Slot", on_click=log_count, args=(item_to_count,), use_container_width=True, type="primary")

        # Display the live total for the current item
        st.metric(f"Total Counted for {item_to_count}", f"{sum(st.session_state.master_inventory_counts.get(item_to_count, [])):.2f}")

        # --- Display and Edit Partial Counts ---
        st.markdown("###### Edit Logged Counts (up to 6 locations):")
        partial_counts = st.session_state.master_inventory_counts.get(item_to_count, [])
        # Ensure there are always 6 slots available for editing
        while len(partial_counts) < 6:
            partial_counts.append(0)

        cols = st.columns(6)
        new_counts = []
        for i in range(6):
            new_count = cols[i].number_input(f"Loc {i+1}", value=float(partial_counts[i]), key=f"{item_to_count}_{i}", step=1.0, format="%.1f")
            new_counts.append(new_count)

        # Update the state only if there was a change
        if new_counts != st.session_state.master_inventory_counts.get(item_to_count, []):
            st.session_state.master_inventory_counts[item_to_count] = new_counts
            st.rerun()



        st.markdown("---")
        st.markdown("#### Final Inventory Summary")
        counted_data = []
        for item, counts in st.session_state.master_inventory_counts.items():
            if sum(counts) > 0:
                counted_data.append({"Item": item, "Total Count": sum(counts)})

        if counted_data:
            counted_df = pd.DataFrame(counted_data).sort_values(by="Item")
            st.dataframe(counted_df, use_container_width=True, hide_index=True)

            st.markdown("---")
            if st.button("✅ Finalize & Generate New BEVWEEKLY File", use_container_width=True):
                with st.spinner("Generating your new Excel file..."):
                    output_buffer = BytesIO()
                    with pd.ExcelWriter(output_buffer, engine='xlsxwriter') as writer:
                        # Read all sheets from the originally uploaded file
                        all_sheets = {name: pd.read_excel(uploaded_file, sheet_name=name) for name in sheet_names}

                        target_sheet_df = all_sheets[selected_week].copy()
                        inventory_col_name = target_sheet_df.columns[7]

                        # Use a clean copy of the original item column for matching
                        original_items_col = pd.read_excel(uploaded_file, sheet_name=selected_week, usecols=[0], skiprows=4).iloc[:, 0]

                        for item, counts in st.session_state.master_inventory_counts.items():
                            total_count = sum(counts)
                            if total_count > 0:
                                # Find the exact row index in the original, un-processed sheet
                                mask = original_items_col == item
                                if mask.any():
                                    row_index = mask.idxmax()
                                    target_sheet_df.loc[row_index, inventory_col_name] = total_count

                        all_sheets[selected_week] = target_sheet_df
                        for sheet_name, df_to_write in all_sheets.items():
                            df_to_write.to_excel(writer, sheet_name=sheet_name, index=False)

                    output_buffer.seek(0)
                    st.success("Your new BEVWEEKLY file is ready to download!")
                    st.download_button(
                        label="📥 Download New BEVWEEKLY.xlsx",
                        data=output_buffer,
                        file_name=f"UPDATED_{uploaded_file.name}",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
        else:
            st.info("No items have been counted yet for this week.")
