import streamlit as st
import pandas as pd
from datetime import datetime
import re
import math
from io import BytesIO
import json
import os

# --- Page Configuration (MUST BE THE FIRST STREAMLIT COMMAND) ---
st.set_page_config(page_title="Bev Usage Analyzer", layout="wide")
st.title("🍺 Bev Usage Analyzer")

# --- Constants ---
LAYOUT_FILE = "inventory_layout.json"

# --- Caching the data processing ---
@st.cache_data
def load_and_process_data(uploaded_file):
    """
    Reads the uploaded Excel file, processes all data, and calculates summary metrics.
    This function is cached to prevent re-running on every widget interaction.
    """
    xls = pd.ExcelFile(uploaded_file)
    sheet_names = xls.sheet_names

    original_order_df = xls.parse(sheet_names[0], skiprows=4)
    original_order = original_order_df.iloc[:, 0].dropna().astype(str).tolist()

    compiled_data = []
    for sheet in sheet_names:
        try:
            df = xls.parse(sheet, skiprows=4)
            df = df.rename(columns={
                df.columns[0]: 'Item', df.columns[9]: 'Usage', df.columns[7]: 'End Inventory'
            })
            df = df[['Item', 'Usage', 'End Inventory']]
            df['Week'] = sheet
            date_value = xls.parse(sheet).iloc[1, 0]
            df['Date'] = pd.to_datetime(date_value) if isinstance(date_value, datetime) else pd.NaT
            compiled_data.append(df)
        except Exception:
            continue
            
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
    summary_df['Item'] = summary_df['Item'].astype(str)
    original_order_cleaned = [item.strip() for item in original_order]
    summary_df['ItemOrder'] = summary_df['Item'].apply(lambda x: original_order_cleaned.index(x) if x in original_order_cleaned else float('inf'))
    summary_df = summary_df.sort_values(by='ItemOrder').drop(columns='ItemOrder')
    
    vendor_map = {
        "Breakthru": ["WHISKEY Buffalo Trace", "WHISKEY Bulleit Straight Rye", "WHISKEY Crown Royal", "WHISKEY Crown Royal Regal Apple", "WHISKEY Fireball Cinnamon", "WHISKEY Jack Daniels Black", "WHISKEY Jack Daniels Tennessee Fire", "VODKA Deep Eddy Lime", "VODKA Deep Eddy Orange", "VODKA Deep Eddy Ruby Red", "VODKA Fleischmann's Cherry", "VODKA Fleischmann's Grape", "VODKA Ketel One", "LIQ Amaretto", "LIQ Baileys Irish Cream", "LIQ Chambord", "LIQ Melon", "LIQ Rumpleminze", "LIQ Triple Sec", "LIQ Blue Curacao", "LIQ Butterscotch", "LIQ Peach Schnapps", "LIQ Sour Apple", "LIQ Watermelon Schnapps", "BRANDY Well", "GIN Well", "RUM Well", "SCOTCH Well", "TEQUILA Well", "VODKA Well", "WHISKEY Well", "GIN Tanqueray", "TEQUILA Casamigos Blanco", "TEQUILA Corazon Reposado", "TEQUILA Don Julio Blanco", "RUM Captain Morgan Spiced", "WINE LaMarca Prosecco", "WINE William Wycliff Brut Chateauamp", "BAR CONS Bloody Mary", "JUICE Red Bull", "JUICE Red Bull SF", "JUICE Red Bull Yellow"],
        "Southern": ["WHISKEY Basil Hayden", "WHISKEY Jameson", "WHISKEY Jim Beam", "WHISKEY Makers Mark", "WHISKEY Skrewball Peanut Butter", "VODKA Grey Goose", "VODKA Titos", "TEQUILA Cazadores Reposado", "TEQUILA Patron Silver", "RUM Bacardi Superior White", "RUM Malibu Coconut", "WHISKEY Dewars White Label", "WHISKEY Glenlivet", "LIQ Grand Marnier", "LIQ Jagermeister", "LIQ Kahlua", "LIQ Vermouth Dry", "LIQ Vermouth Sweet", "WINE Kendall Jackson Chardonnay", "WINE La Crema Chardonnay", "WINE La Crema Pinot Noir", "WINE Troublemaker Red", "WINE Villa Sandi Pinot Grigio", "BAR CONS Bitters", "BAR CONS Simple Syrup"],
        "RNDC": ["WHISKEY Four Roses", "GIN Hendricks", "TEQUILA Milagro Anejo", "TEQUILA Milagro Reposado", "TEQUILA Milagro Silver", "WINE Infamous Goose Sauv Blanc", "WINE Salmon Creek Cab", "WINE Salmon Creek Chard", "WINE Salmon Creek Merlot", "WINE Salmon Creek White Zin", "BAR CONS Mango Puree"],
        "Crescent": ["BEER DFT Alaskan Amber", "BEER DFT Blue Moon Belgian White", "BEER DFT Coors Light", "BEER DFT Dos Equis Lager", "BEER DFT Miller Lite", "BEER DFT Modelo Especial", "BEER DFT New Belgium Juicy Haze IPA", "BEER BTL Coors Banquet", "BEER BTL Coors Light", "BEER BTL Miller Lite", "BEER BTL Angry Orchard Crisp Apple", "BEER BTL College Street Big Blue Van", "BEER BTL Corona NA", "BEER BTL Corona Extra", "BEER BTL Corona Premier", "BEER BTL Coronita Extra", "BEER BTL Dos Equis Lager", "BEER BTL Guinness", "BEER BTL Heineken 0.0", "BEER BTL Modelo Especial", "BEER BTL Pacifico", "BEER BTL Truly Pineapple", "BEER BTL Truly Wild Berry", "BEER BTL Twisted Tea", "BEER BTL White Claw Black Cherry", "BEER BTL White Claw Mango", "BEER BTL White Claw Peach", "JUICE Ginger Beer", "VODKA Western Son Blueberry", "VODKA Western Son Lemon", "VODKA Western Son Original", "VODKA Western Son Prickly Pear", "VODKA Western Son Raspberry"],
        "Hensley": ["BEER DFT Bud Light", "BEER DFT Church Music", "BEER DFT Firestone Walker 805", "BEER DFT Michelob Ultra", "BEER DFT Mother Road Sunday Drive", "BEER DFT Tower Station", "BEER BTL Bud Light", "BEER BTL Budweiser", "BEER BTL Michelob Ultra", "BEER BTL Austin Eastciders"]
    }
    for vendor, items in vendor_map.items(): vendor_map[vendor] = [item.strip() for item in items]
    
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

    if app_mode == "Analyze Past Usage & Plan Orders":
        try:
            summary_df, vendor_map, category_map = load_and_process_data(uploaded_file)
        except Exception as e:
            st.error(f"An error occurred during data processing: {e}")
            st.stop()
        tab_summary, tab_ordering_worksheet = st.tabs(["📊 Summary", "🧪 Ordering Worksheet"])
        
        with tab_summary:
            st.subheader("Usage Summary")
            # This tab is complete and fully functional
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
            styled_df = display_df.style.format(format_dict, na_rep="-").applymap(
                highlight_weeks_remaining, threshold=threshold,
                subset=['Weeks Remaining (YTD)', 'Weeks Remaining (10 Wk)', 'Weeks Remaining (4 Wk)', 'Weeks Remaining (ATH)', 'Weeks Remaining (Lowest 4)', 'Weeks Remaining (Highest 4)']
            )
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            csv = display_df.to_csv(index=False).encode('utf-8')
            st.download_button("Download Summary CSV", data=csv, file_name="beverage_summary.csv")

        with tab_ordering_worksheet:
            st.subheader("🧪 Ordering Worksheet: Inventory Planning")
        mode = st.selectbox("Select View Mode:", ["By Vendor", "By Category"])
        base_items = []
        filter_selection = None
        if mode == "By Vendor":
            vendor = st.selectbox("Select Vendor", list(vendor_map.keys()), key="vendor_select")
            base_items = vendor_map.get(vendor, [])
            filter_selection = vendor
        else:
            selected_category = st.selectbox("Select Category", list(category_map.keys()), key="category_select")
            base_items = category_map.get(selected_category, [])
            filter_selection = selected_category
        usage_option = st.selectbox(
            "Select usage average for calculation:",
            options=['10-Week Average', '4-Week Average', 'Year-to-Date Average', 'Lowest 4 Average (non-zero)', 'Highest 4 Average'],
            index=1, key="usage_radio"
        )
        
        # --- NEW: Master Slider Control ---
        st.markdown("---")
        col1, col2 = st.columns([3, 1])
        col1, col2 = st.columns(2)
        with col1:
            bulk_week_target = st.slider(
                "Set a target for all items below:",
                min_value=0.0, max_value=12.0, value=4.0, step=0.5, key="bulk_week_slider"
            )
            mode = st.selectbox("Select View Mode:", ["By Vendor", "By Category"], key="worksheet_mode")
        with col2:
            st.write("") # Spacer
            if st.button("Apply Target to All", use_container_width=True):
                df_to_update = st.session_state.worksheet_df.copy()
                df_to_update['Target Weeks of Supply'] = bulk_week_target
                df_to_update['Order Qty (Bottles)'] = df_to_update.apply()
                lambda r: max(0, int(math.ceil((r['Target Weeks of Supply'] * r['Selected Avg']) - r['On Hand']))) if r['Selected Avg'] > 0 else 0,
                axis=1
            usage_option = st.selectbox(
                "Select usage average for all tables:",
                options=['10-Week Average', '4-Week Average', 'Year-to-Date Average', 'Lowest 4 Average (non-zero)', 'Highest 4 Average'],
                index=1, key="usage_radio"
            )
        
        def render_worksheet_table(items_to_display, key_prefix):
            worksheet_state_key = f"worksheet_df_{key_prefix}"
            usage_state_key = f"usage_option_{key_prefix}"

            # Master slider and Apply button
            st.markdown("---")
            col1, col2 = st.columns([3, 1])
            with col1:
                bulk_week_target = st.slider(
                    "Set a target for all items in this tab:",
                    min_value=0.0, max_value=12.0, value=4.0, step=0.5, key=f"slider_{key_prefix}"
                )
                st.session_state.worksheet_df = df_to_update
        st.markdown("---")
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
                        st.markdown("---")
            
                        if worksheet_state_key not in st.session_state or st.session_state.get(usage_state_key) != usage_option:
                            filtered_df = summary_df[summary_df['Item'].isin(items_to_display)]
                editor_df_data = {
                    'Item': filtered_df['Item'], 'On Hand': filtered_df['On Hand'],
                    'Selected Avg': filtered_df[usage_option], 'Order Qty (Bottles)': 0, 'Target Weeks of Supply': 0.0
                }
                worksheet_df = pd.DataFrame(editor_df_data).reset_index(drop=True)
                worksheet_df['Selected Avg'] = pd.to_numeric(worksheet_df['Selected Avg'], errors='coerce').fillna(0)
                def temp_safe_div(n, d):
                    return round(n / d, 1) if d and pd.notna(d) and d > 0 else 0.0
                worksheet_df['Current Wks Left'] = worksheet_df.apply(lambda row: temp_safe_div(row['On Hand'], row['Selected Avg']), axis=1)
                st.session_state[worksheet_state_key] = worksheet_df[['Item', 'On Hand', 'Current Wks Left', 'Selected Avg', 'Order Qty (Bottles)', 'Target Weeks of Supply']]
                st.session_state[usage_state_key] = usage_option
                if 'last_edited_column' in st.session_state: st.session_state.last_edited_column = None
                st.rerun()

        worksheet_state_key = f"worksheet_df_{mode}_{filter_selection}_{usage_option}"
        if 'current_worksheet_key' not in st.session_state or st.session_state.current_worksheet_key != worksheet_state_key:
            filtered_df = summary_df[summary_df['Item'].isin(base_items)]
            editor_df_data = {
                'Item': filtered_df['Item'], 'On Hand': filtered_df['On Hand'],
                'Selected Avg': filtered_df[usage_option], 'Order Qty (Bottles)': 0, 'Target Weeks of Supply': 0.0
            }
            worksheet_df = pd.DataFrame(editor_df_data)
            worksheet_df['Selected Avg'] = pd.to_numeric(worksheet_df['Selected Avg'], errors='coerce').fillna(0)
            def temp_safe_div(n, d):
                return round(n / d, 1) if d and pd.notna(d) and d > 0 else 0.0
            worksheet_df['Current Wks Left'] = worksheet_df.apply(lambda row: temp_safe_div(row['On Hand'], row['Selected Avg']), axis=1)
            st.session_state.worksheet_df = worksheet_df[['Item', 'On Hand', 'Current Wks Left', 'Selected Avg', 'Order Qty (Bottles)', 'Target Weeks of Supply']]
            st.session_state.current_worksheet_key = worksheet_state_key
            st.session_state.last_edited_column = None
        
        edited_df = st.data_editor(
            st.session_state.worksheet_df, hide_index=True, use_container_width=True, key="order_editor",
            column_config={
                "Item": st.column_config.TextColumn(disabled=True),
                "On Hand": st.column_config.NumberColumn(format="%.2f", disabled=True),
                "Current Wks Left": st.column_config.NumberColumn(format="%.1f", help="Current inventory in terms of weeks of supply.", disabled=True),
                "Selected Avg": st.column_config.NumberColumn(f"Avg Usage ({usage_option})", format="%.2f", disabled=True),
                "Order Qty (Bottles)": st.column_config.NumberColumn(min_value=0, step=1, format="%d"),
                "Target Weeks of Supply": st.column_config.NumberColumn(help="Enter a target total weeks of supply to calculate bottles needed.", min_value=0.0, step=0.5, format="%.1f")
            }
        )
        
        if not edited_df.equals(st.session_state.worksheet_df):
            if not edited_df['Order Qty (Bottles)'].equals(st.session_state.worksheet_df['Order Qty (Bottles)']):
                st.session_state.last_edited_column = 'Bottles'
            elif not edited_df['Target Weeks of Supply'].equals(st.session_state.worksheet_df['Target Weeks of Supply']):
                st.session_state.last_edited_column = 'Weeks'
            edited_df = st.data_editor(
                st.session_state[worksheet_state_key], hide_index=True, use_container_width=True, key=f"editor_{key_prefix}",
                column_config={
                    "Item": st.column_config.TextColumn(disabled=True),
                    "On Hand": st.column_config.NumberColumn(format="%.2f", disabled=True),
                    "Current Wks Left": st.column_config.NumberColumn(format="%.1f", help="Current inventory in weeks of supply.", disabled=True),
                    "Selected Avg": st.column_config.NumberColumn(f"Avg Usage", format="%.2f", disabled=True),
                    "Order Qty (Bottles)": st.column_config.NumberColumn(min_value=0, step=1, format="%d"),
                    "Target Weeks of Supply": st.column_config.NumberColumn(help="Enter a target total weeks of supply", min_value=0.0, step=0.5, format="%.1f")
                }
            )

            new_df = edited_df.copy()
            if st.session_state.last_edited_column == 'Bottles':
                new_df['Target Weeks of Supply'] = new_df.apply(lambda r: (r['On Hand'] + r['Order Qty (Bottles)']) / r['Selected Avg'] if r['Selected Avg'] > 0 else 0, axis=1)
            elif st.session_state.last_edited_column == 'Weeks':
                new_df['Order Qty (Bottles)'] = new_df.apply(
                    lambda r: max(0, int(math.ceil((r['Target Weeks of Supply'] * r['Selected Avg']) - r['On Hand']))) if r['Selected Avg'] > 0 else 0,
                    axis=1
                )
            st.session_state.worksheet_df = new_df
            st.rerun()
            if not edited_df.equals(st.session_state[worksheet_state_key]):
                if not edited_df['Order Qty (Bottles)'].equals(st.session_state[worksheet_state_key]['Order Qty (Bottles)']):
                    st.session_state.last_edited_column = 'Bottles'
                elif not edited_df['Target Weeks of Supply'].equals(st.session_state[worksheet_state_key]['Target Weeks of Supply']):
                    st.session_state.last_edited_column = 'Weeks'
                new_df = edited_df.copy()
                if st.session_state.last_edited_column == 'Bottles':
                    new_df['Target Weeks of Supply'] = new_df.apply(lambda r: (r['On Hand'] + r['Order Qty (Bottles)']) / r['Selected Avg'] if r['Selected Avg'] > 0 else 0, axis=1)
                elif st.session_state.last_edited_column == 'Weeks':
                    new_df['Order Qty (Bottles)'] = new_df.apply(lambda r: max(0, int(math.ceil((r['Target Weeks of Supply'] * r['Selected Avg']) - r['On Hand']))) if r['Selected Avg'] > 0 else 0, axis=1)
                st.session_state[worksheet_state_key] = new_df
                st.rerun()

        st.markdown("---")
        if st.button("Generate Final Order Summary"):
            results = []
            order_df = st.session_state.worksheet_df
            items_to_order = order_df[order_df['Order Qty (Bottles)'] > 0]
            if not items_to_order.empty:
                for _, row in items_to_order.iterrows():
                    on_hand = row['On Hand']
                    bottles_to_order = row['Order Qty (Bottles)']
                    new_total_on_hand = on_hand + bottles_to_order
                    new_weeks_supply = 0.0
                    if row['Selected Avg'] > 0:
                        new_weeks_supply = (on_hand + bottles_to_order) / row['Selected Avg']
                    results.append({
                        'Item': row['Item'], 'Current On Hand': on_hand,
                        'Bottles to Order': int(bottles_to_order),
                        'New Total On Hand': round(new_total_on_hand, 2),
                        'New Weeks of Supply': round(new_weeks_supply, 1)
                    })
                result_df = pd.DataFrame(results)
                st.subheader("Final Order Summary")
                st.dataframe(result_df, use_container_width=True, hide_index=True)
                csv_order = result_df.to_csv(index=False).encode('utf-8')
                st.download_button("Download Final Order CSV", data=csv_order, file_name="final_order_summary.csv")
            else:
                st.warning("No items have been added to the order.")
            # --- NEW: Keg Counter Logic ---
            views_with_keg_counter = ["Crescent", "Hensley", "Draft Beer"]
            if key_prefix in views_with_keg_counter:
                current_order_df = st.session_state.get(worksheet_state_key, pd.DataFrame())
                if not current_order_df.empty:
                    draft_beer_items = category_map.get("Draft Beer", [])
                    kegs_on_order = current_order_df[current_order_df['Item'].isin(draft_beer_items)]
                    total_kegs_ordered = kegs_on_order['Order Qty (Bottles)'].sum()
                    st.metric(label="Total Kegs to Order in this Tab", value=f"{total_kegs_ordered:,.0f}")

            st.markdown("---")
            if st.button("Generate Final Order Summary", key=f"finalize_{key_prefix}"):
                # Logic for this button remains the same
                pass



    elif app_mode == "Configure Inventory Layout":
        st.subheader("⚙️ Configure Inventory Count Layout")
        st.markdown("Here you can define physical locations and the order of items within them to make inventory counting faster.")
        if 'inventory_layout' not in st.session_state:
            try:
                with open(LAYOUT_FILE, 'r') as f:
                    st.session_state.inventory_layout = json.load(f)
            except FileNotFoundError:
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
                    if 'swap_item_info' in st.session_state and st.session_state.swap_item_info[0] == location_to_remove:
                        del st.session_state.swap_item_info
                    st.rerun()
        st.markdown("---")
        st.markdown("##### 2. Assign Items and Set Count Order")
        if not st.session_state.inventory_layout:
            st.warning("Please add at least one location to begin.")
        else:
            xls = pd.ExcelFile(uploaded_file)
            all_items = sorted(pd.read_excel(xls, sheet_name=xls.sheet_names[0], skiprows=4).iloc[:, 0].dropna().astype(str).str.strip().tolist())
            all_items = [item for item in all_items if not item.upper().startswith('TOTAL')]
            location_tabs = st.tabs(list(st.session_state.inventory_layout.keys()))
            for i, tab in enumerate(location_tabs):
                location_name = list(st.session_state.inventory_layout.keys())[i]
                with tab:
                    st.markdown(f"#### Edit Layout for: **{location_name}**")
                    assigned_items_in_this_loc = st.session_state.inventory_layout[location_name]
                    available_items = [item for item in all_items if item not in assigned_items_in_this_loc]
                    items_to_add = st.multiselect("Select items to add to this location:", options=available_items, key=f"add_{location_name}")
                    if st.button("Add Selected Items", key=f"add_btn_{location_name}"):
                        st.session_state.inventory_layout[location_name].extend(items_to_add)
                        st.rerun()
                    st.markdown("**Items in this location:**")
                    if assigned_items_in_this_loc:
                        for item_index, item_name in enumerate(assigned_items_in_this_loc):
                            item_cols = st.columns([0.5, 0.1, 0.1, 0.1, 0.1])
                            item_cols[0].markdown(f"**{item_index + 1}.** {item_name}")
                            if item_cols[1].button("⬆️", key=f"up_{location_name}_{item_index}", use_container_width=True):
                                if item_index > 0:
                                    st.session_state.inventory_layout[location_name].insert(item_index - 1, st.session_state.inventory_layout[location_name].pop(item_index))
                                    st.rerun()
                            if item_cols[2].button("⬇️", key=f"down_{location_name}_{item_index}", use_container_width=True):
                                if item_index < len(assigned_items_in_this_loc) - 1:
                                    st.session_state.inventory_layout[location_name].insert(item_index + 1, st.session_state.inventory_layout[location_name].pop(item_index))
                                    st.rerun()
                            if item_cols[3].button("🔁", key=f"swap_{location_name}_{item_index}", use_container_width=True):
                                st.session_state.swap_item_info = (location_name, item_index)
                                st.rerun()
                            if item_cols[4].button("🗑️", key=f"del_{location_name}_{item_index}", use_container_width=True):
                                st.session_state.inventory_layout[location_name].pop(item_index)
                                st.rerun()
                            if 'swap_item_info' in st.session_state and st.session_state.swap_item_info == (location_name, item_index):
                                swap_cols = st.columns([3,1])
                                with swap_cols[0]:
                                    swap_with = st.selectbox("Swap with:", options=[item for item in all_items if item not in assigned_items_in_this_loc], key=f"swap_select_{location_name}_{item_index}", label_visibility="collapsed")
                                with swap_cols[1]:
                                    if st.button("Confirm Swap", key=f"confirm_swap_{location_name}_{item_index}"):
                                        st.session_state.inventory_layout[location_name][item_index] = swap_with
                                        del st.session_state.swap_item_info
                                        st.rerun()
        st.markdown("---")
        if st.button("💾 Save Layout to File", type="primary", use_container_width=True):
            with open(LAYOUT_FILE, 'w') as f:
                json.dump(st.session_state.inventory_layout, f, indent=4)
            st.success("Inventory layout saved successfully!")

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

