import streamlit as st
import pandas as pd
from datetime import datetime
import re

# --- Page Configuration (MUST BE THE FIRST STREAMLIT COMMAND) ---
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
        
    return summary_df, full_df, vendor_map, category_map

# --- Main App UI ---
uploaded_file = st.file_uploader("Upload your BEVWEEKLY Excel File", type="xlsx")

if uploaded_file:
    try:
        summary_df, full_df, vendor_map, category_map = load_and_process_data(uploaded_file)
    except Exception as e:
        st.error(f"An error occurred during data processing: {e}")
        st.stop()

    tab_summary, tab_ordering_worksheet, tab_sales_analysis = st.tabs(["📊 Summary", "🧪 Ordering Worksheet", "🔬 Sales Mix Analysis"])

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
        st.download_button("Download Summary CSV", data=csv, file_name=download_filename)

    with tab_ordering_worksheet:
        # This tab's logic is complete and unchanged
        pass

    with tab_sales_analysis:
        st.subheader("Sales vs. Actual Usage Variance")
        st.markdown("This tool scans your Sales Mix report to compare what you sold to what you actually used.")
        
        with st.expander("Click to view Sales Mix Configuration"):
            st.warning("This configuration will be required when analyzing Draft, Liquor, and Wine.")
            VOLUME_CONFIG = {"16oz": 16, "32oz": 32, "Pitcher": 64, "Liquor Pour": 1.5, "Wine Pour": 6, "Half Barrel Keg": 1984, "Sixtel Keg": 661, "Standard Liquor/Wine Bottle": 25.4, "Liter Liquor Bottle": 33.8}
            st.json(VOLUME_CONFIG)
            ITEM_CONTAINER_MAP = {"BEER DFT Alaskan Amber": "Half Barrel Keg", "WHISKEY Buffalo Trace": "Standard Liquor/Wine Bottle"}
            st.json(ITEM_CONTAINER_MAP)

        sales_mix_file = st.file_uploader("Upload Weekly Sales Mix File", type=["txt", "csv"])

        if sales_mix_file:
            try:
                # Read the file as raw lines of text
                sales_mix_file.seek(0)
                sales_lines = [line.decode('utf-8').strip() for line in sales_mix_file.readlines()]

                # --- NEW: Display the raw text file for debugging ---
                with st.expander("Click to view content of uploaded Sales Mix file"):
                    st.code('\n'.join(sales_lines))

                st.markdown("---")
                st.markdown("#### Please confirm the position of your quantity number:")
                qty_position = st.number_input(
                    "On a line with a sold item, which number from the end is the quantity? (1 = last, 2 = second-to-last)",
                    min_value=1, value=1, step=1,
                    help="If a line reads '123 Bud Light... 45', the quantity is the 1st number from the end. If it reads 'Bud Light 45 ... 123', it's the 2nd number from the end."
                )

                all_inventory_items = list(summary_df['Item'].unique())
                item_lookup = {re.sub(r'^(BEER BTL|BEER DFT|WHISKEY|VODKA|LIQ|GIN|RUM|SCOTCH|TEQUILA|WINE)\s+', '', item).upper(): item for item in all_inventory_items}
                
                sales_counts = {}
                for line in sales_lines:
                    if not line: continue
                    found_item = None
                    for base_name, full_name in item_lookup.items():
                        # Use word boundaries for more precise matching
                        if re.search(r'\b' + re.escape(base_name) + r'\b', line.upper()):
                            found_item = full_name
                            break
                    
                    if found_item:
                        numbers_on_line = re.findall(r'\d+\.?\d*', line)
                        if len(numbers_on_line) >= qty_position:
                            qty_sold = float(numbers_on_line[-qty_position])
                            sales_counts[found_item] = sales_counts.get(found_item, 0) + qty_sold
                
                # --- Variance Calculation ---
                variance_data = []
                latest_date = full_df['Date'].max()
                actual_usage_df = full_df[full_df['Date'] == latest_date][['Item', 'Usage']].set_index('Item')

                for item, qty_sold in sales_counts.items():
                    theoretical_usage = qty_sold
                    actual_usage = actual_usage_df.loc[item, 'Usage'] if item in actual_usage_df.index else 0
                    variance = actual_usage - theoretical_usage
                    variance_data.append({
                        "Item": item, "Actual Usage": actual_usage,
                        "Theoretical Usage (Sold)": theoretical_usage, "Variance": variance
                    })

                if variance_data:
                    variance_df = pd.DataFrame(variance_data)
                    def style_variance(val):
                        if abs(val) >= 2: return 'background-color: #ff4b4b'
                        elif abs(val) >= 1: return 'background-color: #ffb400'
                        return ''
                    
                    st.markdown("---")
                    st.subheader("Variance Report (Unit-Based)")
                    st.markdown("_Note: This view assumes all sold items are 1-to-1 units (like bottled beer). Volume calculations for draft/liquor will be added next._")
                    st.dataframe(
                        variance_df.style.format({"Actual Usage": "{:.1f}", "Theoretical Usage (Sold)": "{:.0f}", "Variance": "{:+.1f}"}).applymap(style_variance, subset=['Variance']),
                        use_container_width=True, hide_index=True
                    )
                else:
                    st.warning("No matching items found. Please check your sales mix file.")
            
            except Exception as e:
                st.error(f"Could not process the Sales Mix file. Error: {e}")
