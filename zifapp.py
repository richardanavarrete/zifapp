import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Bev Usage Analyzer", layout="wide")
st.title("🍺 Bev Usage Analyzer")

uploaded_file = st.file_uploader("Upload BEVWEEKLY Excel File", type="xlsx")

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    sheet_names = xls.sheet_names

    # --- Data Ingestion and Cleaning ---
    try:
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
        full_df['Usage'] = pd.to_numeric(full_df['Usage'], errors='coerce')
        full_df['End Inventory'] = pd.to_numeric(full_df['End Inventory'], errors='coerce')
        full_df = full_df.dropna(subset=['Usage', 'End Inventory'])
        full_df = full_df.sort_values(by=['Item', 'Date'])

    except Exception as e:
        st.error(f"An error occurred while processing the Excel file: {e}")
        st.stop()


    # --- Metric Calculation ---
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
            if pd.notna(d) and d > 0:
                return round(n / d, 2)
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
            'Avg of Lowest 4 (non-zero)': round(avg_of_lowest_4_non_zero, 2) if pd.notna(avg_of_lowest_4_non_zero) else None,
            'Avg of Highest 4': round(avg_of_highest_4, 2) if pd.notna(avg_of_highest_4) else None,
            'Wks Rmn (YTD Avg)': safe_div(inventory.iloc[-1], ytd_avg),
            'Wks Rmn (10Wk Avg)': safe_div(inventory.iloc[-1], last_10.mean()),
            'Wks Rmn (4Wk Avg)': safe_div(inventory.iloc[-1], last_4.mean()),
            'Wks Rmn (ATH)': safe_div(inventory.iloc[-1], usage.max()),
            'Wks Rmn (Lowest 4)': safe_div(inventory.iloc[-1], avg_of_lowest_4_non_zero),
            'Wks Rmn (Highest 4)': safe_div(inventory.iloc[-1], avg_of_highest_4)
        })

    summary_df = full_df.groupby('Item').apply(compute_metrics).reset_index()
    summary_df['Item'] = summary_df['Item'].astype(str)
    original_order_cleaned = [item.strip() for item in original_order]
    summary_df['ItemOrder'] = summary_df['Item'].apply(
        lambda x: original_order_cleaned.index(x) if x in original_order_cleaned else float('inf')
    )
    summary_df = summary_df.sort_values(by='ItemOrder').drop(columns='ItemOrder')
    

    # --- UI Tabs ---
    tab_summary, tab_ordering_worksheet = st.tabs(["📊 Summary", "🧪 Ordering Worksheet"])

    with tab_summary:
        st.subheader("Usage Summary")
        threshold = st.slider("Highlight if weeks remaining is below:", min_value=1.0, max_value=10.0, value=2.0, step=0.5)

        def highlight_weeks_remaining(val, threshold=2.0):
            if pd.notna(val) and isinstance(val, (int, float)):
                return 'background-color: #ff4b4b' if val < threshold else ''
            return ''

        format_dict = {col: '{:,.2f}' for col in summary_df.select_dtypes(include=['float64', 'float32']).columns}
        
        styled_df = summary_df.style.format(format_dict, na_rep="-").applymap(
            highlight_weeks_remaining, threshold=threshold,
            subset=[
                'Wks Rmn (10Wk Avg)', 'Wks Rmn (4Wk Avg)', 'Wks Rmn (YTD Avg)',
                'Wks Rmn (ATH)', 'Wks Rmn (Lowest 4)', 'Wks Rmn (Highest 4)'
            ]
        )
        st.dataframe(styled_df, use_container_width=True)
        csv = summary_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Summary CSV", data=csv, file_name="beverage_usage_summary.csv")

    with tab_ordering_worksheet:
        st.subheader("🧪 Ordering Worksheet: Inventory Planning")
        mode = st.radio("Select View Mode:", ["By Vendor", "By Category"])

        vendor_map = {
            "Breakthru": ["WHISKEY Buffalo Trace", "WHISKEY Bulleit Straight Rye", "WHISKEY Crown Royal", "WHISKEY Crown Royal Regal Apple", "WHISKEY Fireball Cinnamon", "WHISKEY Jack Daniels Black", "WHISKEY Jack Daniels Tennessee Fire", "VODKA Deep Eddy Lime", "VODKA Deep Eddy Orange", "VODKA Deep Eddy Ruby Red", "VODKA Fleischmann's Cherry", "VODKA Fleischmann's Grape", "VODKA Ketel One", "LIQ Amaretto", "LIQ Baileys Irish Cream", "LIQ Chambord", "LIQ Melon", "LIQ Rumpleminze", "LIQ Triple Sec", "LIQ Blue Curacao", "LIQ Butterscotch", "LIQ Peach Schnapps", "LIQ Sour Apple", "LIQ Watermelon Schnapps", "BRANDY Well", "GIN Well", "RUM Well", "SCOTCH Well", "TEQUILA Well", "VODKA Well", "WHISKEY Well", "GIN Tanqueray", "TEQUILA Casamigos Blanco", "TEQUILA Corazon Reposado", "TEQUILA Don Julio Blanco", "RUM Captain Morgan Spiced", "WINE LaMarca Prosecco", "WINE William Wycliff Brut Chateauamp", "BAR CONS Bloody Mary", "JUICE Red Bull", "JUICE Red Bull SF", "JUICE Red Bull Yellow"],
            "Southern": ["WHISKEY Basil Hayden", "WHISKEY Jameson", "WHISKEY Jim Beam", "WHISKEY Makers Mark", "WHISKEY Skrewball Peanut Butter", "VODKA Grey Goose", "VODKA Titos", "TEQUILA Cazadores Reposado", "TEQUILA Patron Silver", "RUM Bacardi Superior White", "RUM Malibu Coconut", "WHISKEY Dewars White Label", "WHISKEY Glenlivet", "LIQ Grand Marnier", "LIQ Jagermeister", "LIQ Kahlua", "LIQ Vermouth Dry", "LIQ Vermouth Sweet", "WINE Kendall Jackson Chardonnay", "WINE La Crema Chardonnay", "WINE La Crema Pinot Noir", "WINE Troublemaker Red", "WINE Villa Sandi Pinot Grigio", "BAR CONS Bitters", "BAR CONS Simple Syrup"],
            "RNDC": ["WHISKEY Four Roses", "GIN Hendricks", "TEQUILA Milagro Anejo", "TEQUILA Milagro Reposado", "TEQUILA Milagro Silver", "WINE Infamous Goose Sauv Blanc", "WINE Salmon Creek Cab", "WINE Salmon Creek Chard", "WINE Salmon Creek Merlot", "WINE Salmon Creek White Zin", "BAR CONS Mango Puree"],
            "Crescent": ["BEER DFT Alaskan Amber", "BEER DFT Blue Moon Belgian White", "BEER DFT Coors Light", "BEER DFT Dos Equis Lager", "BEER DFT Miller Lite", "BEER DFT Modelo Especial", "BEER DFT New Belgium Juicy Haze IPA", "BEER BTL Coors Banquet", "BEER BTL Coors Light", "BEER BTL Miller Lite", "BEER BTL Angry Orchard Crisp Apple", "BEER BTL College Street Big Blue Van", "BEER BTL Corona NA", "BEER BTL Corona Extra", "BEER BTL Corona Premier", "BEER BTL Coronita Extra", "BEER BTL Dos Equis Lager", "BEER BTL Guinness", "BEER BTL Heineken 0.0", "BEER BTL Modelo Especial", "BEER BTL Pacifico", "BEER BTL Truly Pineapple", "BEER BTL Truly Wild Berry", "BEER BTL Twisted Tea", "BEER BTL White Claw Black Cherry", "BEER BTL White Claw Mango", "BEER BTL White Claw Peach", "JUICE Ginger Beer", "VODKA Western Son Blueberry", "VODKA Western Son Lemon", "VODKA Western Son Original", "VODKA Western Son Prickly Pear", "VODKA Western Son Raspberry"],
            "Hensley": ["BEER DFT Bud Light", "BEER DFT Church Music", "BEER DFT Firestone Walker 805", "BEER DFT Michelob Ultra", "BEER DFT Mother Road Sunday Drive", "BEER DFT Tower Station", "BEER BTL Bud Light", "BEER BTL Budweiser", "BEER BTL Michelob Ultra", "BEER BTL Austin Eastciders"]
        }
        for vendor, items in vendor_map.items():
            vendor_map[vendor] = [item.strip() for item in items]

        category_map = {cat: [] for cat in ["Well", "Whiskey", "Vodka", "Gin", "T tequila", "Rum", "Scotch", "Liqueur", "Cordials", "Wine", "Draft Beer", "Bottled Beer", "Juice", "Bar Consumables"]}
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

        base_items = []
        if mode == "By Vendor":
            vendor = st.selectbox("Select Vendor", list(vendor_map.keys()), key="vendor_select")
            base_items = vendor_map.get(vendor, [])
        else: # By Category
            selected_categories = st.multiselect("Select Categories", list(category_map.keys()), default=list(category_map.keys()), key="category_multiselect")
            base_items = [item for cat in selected_categories for item in category_map.get(cat, [])]

        usage_option = st.radio(
            "Select usage average for calculation:",
            ["10Wk Avg", "4Wk Avg", "YTD Avg", "Avg of Lowest 4 (non-zero)", "Avg of Highest 4"],
            index=1,
            key="usage_radio"
        )
        
        # --- NEW: Create a dataframe with a STATIC structure for the editor ---
        filtered_df = summary_df[summary_df['Item'].isin(base_items)]
        
        # Create the editor dataframe with fixed column names
        editor_df_data = {
            'Item': filtered_df['Item'],
            'On Hand': filtered_df['End Inv'],
            'Selected Avg': filtered_df[usage_option],
            'Add Bottles': 0.0,
            'Add Weeks': 0.0
        }
        editable_df = pd.DataFrame(editor_df_data)
        editable_df['Selected Avg'] = pd.to_numeric(editable_df['Selected Avg'], errors='coerce').fillna(0)

        # --- Display the data editor with the static structure ---
        edited_df = st.data_editor(
            editable_df,
            num_rows="dynamic",
            use_container_width=True,
            key="order_editor",
            column_config={
                "Item": st.column_config.TextColumn(disabled=True),
                "On Hand": st.column_config.NumberColumn(format="%.2f", disabled=True),
                "Selected Avg": st.column_config.NumberColumn(f"Avg Usage ({usage_option})", format="%.2f", disabled=True),
                "Add Bottles": st.column_config.NumberColumn("Order (Btls)", min_value=0, format="%d"),
                "Add Weeks": st.column_config.NumberColumn("Order (Wks)", min_value=0, format="%d")
            }
        )

        input_mode = st.radio("Select input mode:", ["Add Bottles", "Add Weeks"], horizontal=True)

        if st.button("Calculate Order"):
            results = []
            # Use the 'edited_df' which contains the user's edits
            for _, row in edited_df.iterrows():
                # Use the static column names from the editor
                item, end_inv, avg_usage = row['Item'], row['On Hand'], row['Selected Avg']
                add_bottles, add_weeks = row['Add Bottles'], row['Add Weeks']

                def final_safe_div(n, d):
                    return round(n / d, 2) if d and pd.notna(d) and d > 0 else 0

                if input_mode == "Add Bottles":
                    bottles_to_order = add_bottles
                    weeks_to_order = final_safe_div(end_inv + bottles_to_order, avg_usage)
                else: # Add Weeks
                    target_inv = add_weeks * avg_usage
                    needed_bottles = target_inv - end_inv
                    bottles_to_order = max(0, needed_bottles)
                    weeks_to_order = add_weeks
                
                new_inv = end_inv + bottles_to_order

                results.append({
                    'Item': item,
                    f'Avg Usage ({usage_option})': avg_usage,
                    'On Hand': end_inv,
                    'Current Supply (Wks)': final_safe_div(end_inv, avg_usage),
                    'Bottles to Order': round(bottles_to_order, 2),
                    'Weeks to Order': round(weeks_to_order, 2),
                    'New On Hand': round(new_inv, 2),
                    'New Supply (Wks)': round(weeks_to_order, 2),
                })
            
            if results:
                result_df = pd.DataFrame(results)
                st.dataframe(result_df, use_container_width=True)
                csv_order = result_df.to_csv(index=False).encode('utf-8')
                st.download_button("Download Order CSV", data=csv_order, file_name="beverage_order_worksheet.csv")

    with st.expander("Show Debug Information"):
        st.subheader("Debug Info")
        st.markdown("**Unique Items found in Excel file:**")
        st.write(summary_df['Item'].unique().tolist())
        if base_items:
            st.markdown("**Items currently selected for the worksheet above:**")
            st.write(base_items)
