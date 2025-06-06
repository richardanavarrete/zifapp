import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Bev Usage Analyzer", layout="wide")
st.title("🍺 Bev Usage Analyzer")

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
                df.columns[0]: 'Item',
                df.columns[9]: 'Usage',
                df.columns[7]: 'End Inventory'
            })
            df = df[['Item', 'Usage', 'End Inventory']]
            df['Week'] = sheet
            date_value = xls.parse(sheet).iloc[1, 0]
            if isinstance(date_value, datetime):
                df['Date'] = pd.to_datetime(date_value)
            else:
                df['Date'] = pd.NaT
            compiled_data.append(df)
        except Exception as e:
            st.warning(f"Skipped sheet {sheet}: {e}")
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
        group = group.sort_values(by='Date').reset_index(drop=True)
        usage = group['Usage']
        inventory = group['End Inventory']
        dates = group['Date']
        last_10 = usage.tail(10)
        last_4 = usage.tail(4)
        current_year = datetime.now().year
        ytd_usage = group[dates.dt.year == current_year]['Usage'] if pd.api.types.is_datetime64_any_dtype(dates) else pd.Series(dtype='float64')
        ytd_avg = ytd_usage.mean() if not ytd_usage.empty else None
        def safe_div(n, d):
            if pd.notna(d) and d > 0: return round(n / d, 2)
            return None
        avg_of_highest_4 = usage.nlargest(4).mean() if not usage.empty else None
        non_zero_usage = usage[usage > 0]
        avg_of_lowest_4_non_zero = non_zero_usage.nsmallest(4).mean() if not non_zero_usage.empty else None
        return pd.Series({
            'End Inv': round(inventory.iloc[-1], 2),
            'YTD Avg': round(ytd_avg, 2) if pd.notna(ytd_avg) else None,
            '10Wk Avg': round(last_10.mean(), 2) if not last_10.empty else None,
            '4Wk Avg': round(last_4.mean(), 2) if not last_4.empty else None,
            'AT-High': round(usage.max(), 2),
            'Low4wk Avg': round(avg_of_lowest_4_non_zero, 2) if pd.notna(avg_of_lowest_4_non_zero) else None,
            'High4wk Avg': round(avg_of_highest_4, 2) if pd.notna(avg_of_highest_4) else None,
            'WksRmn(YTD)': safe_div(inventory.iloc[-1], ytd_avg),
            'WksRmn(10Wk)': safe_div(inventory.iloc[-1], last_10.mean()),
            'WksRmn(4Wk)': safe_div(inventory.iloc[-1], last_4.mean()),
            'WksRmn(ATH)': safe_div(inventory.iloc[-1], usage.max()),
            'WksRmn(Lo4)': safe_div(inventory.iloc[-1], avg_of_lowest_4_non_zero),
            'WksRmn(Hi4)': safe_div(inventory.iloc[-1], avg_of_highest_4)
        })

    summary_df = full_df.groupby('Item').apply(compute_metrics).reset_index()
    summary_df['Item'] = summary_df['Item'].astype(str)
    original_order_cleaned = [item.strip() for item in original_order]
    summary_df['ItemOrder'] = summary_df['Item'].apply(
        lambda x: original_order_cleaned.index(x) if x in original_order_cleaned else float('inf')
    )
    summary_df = summary_df.sort_values(by='ItemOrder').drop(columns='ItemOrder')
    
    vendor_map = {
        "Breakthru": ["WHISKEY Buffalo Trace", "WHISKEY Bulleit Straight Rye", "WHISKEY Crown Royal", "WHISKEY Crown Royal Regal Apple", "WHISKEY Fireball Cinnamon", "WHISKEY Jack Daniels Black", "WHISKEY Jack Daniels Tennessee Fire", "VODKA Deep Eddy Lime", "VODKA Deep Eddy Orange", "VODKA Deep Eddy Ruby Red", "VODKA Fleischmann's Cherry", "VODKA Fleischmann's Grape", "VODKA Ketel One", "LIQ Amaretto", "LIQ Baileys Irish Cream", "LIQ Chambord", "LIQ Melon", "LIQ Rumpleminze", "LIQ Triple Sec", "LIQ Blue Curacao", "LIQ Butterscotch", "LIQ Peach Schnapps", "LIQ Sour Apple", "LIQ Watermelon Schnapps", "BRANDY Well", "GIN Well", "RUM Well", "SCOTCH Well", "TEQUILA Well", "VODKA Well", "WHISKEY Well", "GIN Tanqueray", "TEQUILA Casamigos Blanco", "TEQUILA Corazon Reposado", "TEQUILA Don Julio Blanco", "RUM Captain Morgan Spiced", "WINE LaMarca Prosecco", "WINE William Wycliff Brut Chateauamp", "BAR CONS Bloody Mary", "JUICE Red Bull", "JUICE Red Bull SF", "JUICE Red Bull Yellow"],
        "Southern": ["WHISKEY Basil Hayden", "WHISKEY Jameson", "WHISKEY Jim Beam", "WHISKEY Makers Mark", "WHISKEY Skrewball Peanut Butter", "VODKA Grey Goose", "VODKA Titos", "TEQUILA Cazadores Reposado", "TEQUILA Patron Silver", "RUM Bacardi Superior White", "RUM Malibu Coconut", "WHISKEY Dewars White Label", "WHISKEY Glenlivet", "LIQ Grand Marnier", "LIQ Jagermeister", "LIQ Kahlua", "LIQ Vermouth Dry", "LIQ Vermouth Sweet", "WINE Kendall Jackson Chardonnay", "WINE La Crema Chardonnay", "WINE La Crema Pinot Noir", "WINE Troublemaker Red", "WINE Villa Sandi Pinot Grigio", "BAR CONS Bitters", "BAR CONS Simple Syrup"],
        "RNDC": ["WHISKEY Four Roses", "GIN Hendricks", "TEQUILA Milagro Anejo", "TEQUILA Milagro Reposado", "TEQUILA Milagro Silver", "WINE Infamous Goose Sauv Blanc", "WINE Salmon Creek Cab", "WINE Salmon Creek Chard", "WINE Salmon Creek Merlot", "WINE Salmon Creek White Zin", "BAR CONS Mango Puree"],
        "Crescent": ["BEER DFT Alaskan Amber", "BEER DFT Blue Moon Belgian White", "BEER DFT Coors Light", "BEER DFT Dos Equis Lager", "BEER DFT Miller Lite", "BEER DFT Modelo Especial", "BEER DFT New Belgium Juicy Haze IPA", "BEER BTL Coors Banquet", "BEER BTL Coors Light", "BEER BTL Miller Lite", "BEER BTL Angry Orchard Crisp Apple", "BEER BTL College Street Big Blue Van", "BEER BTL Corona NA", "BEER BTL Corona Extra", "BEER BTL Corona Premier", "BEER BTL Coronita Extra", "BEER BTL Dos Equis Lager", "BEER BTL Guinness", "BEER BTL Heineken 0.0", "BEER BTL Modelo Especial", "BEER BTL Pacifico", "BEER BTL Truly Pineapple", "BEER BTL Truly Wild Berry", "BEER BTL Twisted Tea", "BEER BTL White Claw Black Cherry", "BEER BTL White Claw Mango", "BEER BTL White Claw Peach", "JUICE Ginger Beer", "VODKA Western Son Blueberry", "VODKA Western Son Lemon", "VODKA Western Son Original", "VODKA Western Son Prickly Pear", "VODKA Western Son Raspberry"],
        "Hensley": ["BEER DFT Bud Light", "BEER DFT Church Music", "BEER DFT Firestone Walker 805", "BEER DFT Michelob Ultra", "BEER DFT Mother Road Sunday Drive", "BEER DFT Tower Station", "BEER BTL Bud Light", "BEER BTL Budweiser", "BEER BTL Michelob Ultra", "BEER BTL Austin Eastciders"]
    }
    for vendor, items in vendor_map.items():
        vendor_map[vendor] = [item.strip() for item in items]

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

# --- Main App ---
uploaded_file = st.file_uploader("Upload BEVWEEKLY Excel File", type="xlsx")

if uploaded_file:
    try:
        summary_df, vendor_map, category_map = load_and_process_data(uploaded_file)
    except Exception as e:
        st.error(f"An error occurred during data processing: {e}")
        st.stop()

    # --- UI Tabs ---
    tab_summary, tab_ordering_worksheet = st.tabs(["📊 Summary", "🧪 Ordering Worksheet"])

    with tab_summary:
        st.subheader("Usage Summary")
        filter_type = st.radio("Filter By:", ["Vendor", "Category"], horizontal=True, key="summary_filter_type")
        display_df = summary_df
        download_filename = "beverage_summary_full.csv"

        if filter_type == "Vendor":
            vendor_options = ["All Vendors"] + list(vendor_map.keys())
            selected_vendor = st.selectbox("Select Vendor", options=vendor_options, key="summary_vendor_select")
            if selected_vendor != "All Vendors":
                vendor_items = vendor_map.get(selected_vendor, [])
                display_df = summary_df[summary_df['Item'].isin(vendor_items)]
                download_filename = f"beverage_summary_{selected_vendor}.csv"
        
        elif filter_type == "Category":
            category_options = ["All Categories"] + list(category_map.keys())
            selected_category = st.selectbox("Select Category", options=category_options, key="summary_category_select")
            if selected_category != "All Categories":
                category_items = category_map.get(selected_category, [])
                display_df = summary_df[summary_df['Item'].isin(category_items)]
                download_filename = f"beverage_summary_{selected_category}.csv"

        threshold = st.slider("Highlight if weeks remaining is below:", min_value=0.2, max_value=10.0, value=2.0, step=0.1)

        def highlight_weeks_remaining(val, threshold=2.0):
            if pd.notna(val) and isinstance(val, (int, float)):
                return 'background-color: #ff4b4b' if val < threshold else ''
            return ''

        format_dict = {col: '{:,.2f}' for col in display_df.select_dtypes(include=['float64', 'float32']).columns}
        styled_df = display_df.style.format(format_dict, na_rep="-").applymap(
            highlight_weeks_remaining, threshold=threshold,
            subset=['WksRmn(YTD)', 'WksRmn(10Wk)', 'WksRmn(4Wk)', 'WksRmn(ATH)', 'WksRmn(Lo4)', 'WksRmn(Hi4)']
        )
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        csv = display_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Summary CSV", data=csv, file_name=download_filename)

    with tab_ordering_worksheet:
        st.subheader("🧪 Ordering Worksheet: Inventory Planning")
        
        mode = st.selectbox("Select View Mode:", ["By Vendor", "By Category"])
        base_items = []
        filter_selection = None

        if mode == "By Vendor":
            vendor = st.selectbox("Select Vendor", list(vendor_map.keys()), key="vendor_select")
            base_items = vendor_map.get(vendor, [])
            filter_selection = vendor
        else: # By Category
            selected_category = st.selectbox("Select Category", list(category_map.keys()), key="category_select")
            base_items = category_map.get(selected_category, [])
            filter_selection = selected_category

        usage_option = st.selectbox(
            "Select usage average for calculation:",
            options=["10Wk Avg", "4Wk Avg", "YTD Avg", "Low4wk Avg", "High4wk Avg"],
            index=1,
            key="usage_radio"
        )
        input_mode = st.radio("Select input mode:", ["Add Bottles", "Add Weeks"], horizontal=True)

        # --- Interactive Worksheet Logic using Session State ---
        
        # Create a unique key for the session state based on the filters
        worksheet_state_key = f"worksheet_df_{mode}_{filter_selection}_{usage_option}"

        # Initialize or update the worksheet dataframe in session state
        if 'current_worksheet_key' not in st.session_state or st.session_state.current_worksheet_key != worksheet_state_key:
            filtered_df = summary_df[summary_df['Item'].isin(base_items)]
            editor_df_data = {
                'Item': filtered_df['Item'],
                'On Hand': filtered_df['End Inv'],
                'Current Wks Left': 0.0,
                'Selected Avg': filtered_df[usage_option],
                'Add Bottles': 0,
                'Add Weeks': 0
            }
            worksheet_df = pd.DataFrame(editor_df_data)
            worksheet_df['Selected Avg'] = pd.to_numeric(worksheet_df['Selected Avg'], errors='coerce').fillna(0)
            
            def temp_safe_div(n, d):
                return round(n / d, 1) if d and pd.notna(d) and d > 0 else 0.0
            worksheet_df['Current Wks Left'] = worksheet_df.apply(lambda row: temp_safe_div(row['On Hand'], row['Selected Avg']), axis=1)
            
            st.session_state.worksheet_df = worksheet_df[['Item', 'On Hand', 'Current Wks Left', 'Selected Avg', 'Add Bottles', 'Add Weeks']]
            st.session_state.current_worksheet_key = worksheet_state_key

        # The data editor uses the dataframe stored in session state
        edited_df = st.data_editor(
            st.session_state.worksheet_df,
            hide_index=True,
            use_container_width=True,
            key="order_editor",
            column_config={
                "Item": st.column_config.TextColumn(disabled=True),
                "On Hand": st.column_config.NumberColumn(format="%.2f", disabled=True),
                "Current Wks Left": st.column_config.NumberColumn(format="%.1f", help="On Hand / Selected Avg", disabled=True),
                "Selected Avg": st.column_config.NumberColumn(f"Avg Usage ({usage_option})", format="%.2f", disabled=True),
                "Add Bottles": st.column_config.NumberColumn("Order (Bottles)", min_value=0, step=1, format="%d"),
                "Add Weeks": st.column_config.NumberColumn("Order (Weeks)", min_value=0, step=1, format="%d")
            }
        )

        # --- Perform interactive calculations ---
        # Compare the edited dataframe with the one in session state to see if a change was made
        if not edited_df.equals(st.session_state.worksheet_df):
            if input_mode == 'Add Bottles':
                # User is typing in 'Add Bottles', so we calculate 'Add Weeks'
                st.session_state.worksheet_df['Add Bottles'] = edited_df['Add Bottles']
                st.session_state.worksheet_df['Add Weeks'] = st.session_state.worksheet_df.apply(
                    lambda row: round((row['On Hand'] + row['Add Bottles']) / row['Selected Avg']) if row['Selected Avg'] > 0 else 0,
                    axis=1
                )
            elif input_mode == 'Add Weeks':
                # User is typing in 'Add Weeks', so we calculate 'Add Bottles'
                st.session_state.worksheet_df['Add Weeks'] = edited_df['Add Weeks']
                st.session_state.worksheet_df['Add Bottles'] = st.session_state.worksheet_df.apply(
                    lambda row: max(0, round((row['Add Weeks'] * row['Selected Avg']) - row['On Hand'])),
                    axis=1
                )
            st.rerun()

        # --- Final Calculation Button ---
        if st.button("Calculate Final Order"):
            results = []
            for _, row in st.session_state.worksheet_df.iterrows():
                # This logic now uses the fully updated session state dataframe
                item, end_inv, avg_usage = row['Item'], row['On Hand'], row['Selected Avg']
                bottles_to_order, weeks_to_order = row['Add Bottles'], row['Add Weeks']
                new_inv = end_inv + bottles_to_order

                def final_safe_div(n, d):
                    return round(n / d, 2) if d and pd.notna(d) and d > 0 else 0
                
                results.append({
                    'Item': item,
                    f'Avg Usage ({usage_option})': avg_usage,
                    'On Hand': end_inv,
                    'Current Supply (Wks)': final_safe_div(end_inv, avg_usage),
                    'Bottles to Order': round(bottles_to_order, 2),
                    'Weeks to Order': round(weeks_to_order, 2),
                    'New On Hand': round(new_inv, 2),
                    'New Supply (Wks)': weeks_to_order,
                })
            
            if results:
                result_df = pd.DataFrame(results)
                st.subheader("Final Order Calculation")
                st.dataframe(result_df, use_container_width=True, hide_index=True)
                csv_order = result_df.to_csv(index=False).encode('utf-8')
                st.download_button("Download Order CSV", data=csv_order, file_name="beverage_order_worksheet.csv")

    with st.expander("Show Debug Information"):
        st.subheader("Debug Info")
        st.markdown("**Unique Items found in Excel file:**")
        st.write(summary_df['Item'].unique().tolist())
        if 'base_items' in locals() and base_items:
            st.markdown("**Items currently selected for the worksheet above:**")
            st.write(base_items)
