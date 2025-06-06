import streamlit as st
import pandas as pd
from datetime import datetime
import re # Import the regular expressions library

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
            'End Inv': round(inventory.iloc[-1], 2), 'YTD Avg': round(ytd_avg, 2) if pd.notna(ytd_avg) else None,
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
uploaded_file = st.file_uploader("Upload BEVWEEKLY Excel File", type="xlsx")

if uploaded_file:
    try:
        summary_df, full_df, vendor_map, category_map = load_and_process_data(uploaded_file)
    except Exception as e:
        st.error(f"An error occurred during data processing: {e}")
        st.stop()

    tab_summary, tab_ordering_worksheet, tab_sales_analysis = st.tabs(["📊 Summary", "🧪 Ordering Worksheet", "🔬 Sales Mix Analysis"])

    with tab_summary:
        # Code for this tab is complete and works...
        pass

    with tab_ordering_worksheet:
        # Code for this tab is complete and works...
        pass

    # --- Sales Mix Analysis Tab ---
    with tab_sales_analysis:
        st.subheader("Sales vs. Actual Usage Variance")
        st.markdown("""
        This tool scans your text-based Sales Mix report to compare what you **sold** to what you **actually used**.
        **NOTE:** This version is designed to work with simple, single-line items like **Bottled Beer and Liquor**. Draft beer is not yet supported.
        """)

        sales_mix_file = st.file_uploader("Upload Weekly Sales Mix File", type=["txt", "csv"])

        if sales_mix_file:
            try:
                # --- New Text-Scanning Logic ---
                sales_mix_lines = [line.decode('utf-8').strip() for line in sales_mix_file.readlines()]
                
                # Create a list of items we can easily parse (bottled beer, liquor, wine)
                simple_parse_items = (
                    category_map.get("Bottled Beer", []) +
                    category_map.get("Whiskey", []) +
                    category_map.get("Vodka", []) +
                    category_map.get("Gin", []) +
                    category_map.get("Tequila", []) +
                    category_map.get("Rum", []) +
                    category_map.get("Scotch", []) +
                    category_map.get("Liqueur", []) +
                    category_map.get("Cordials", []) +
                    category_map.get("Wine", [])
                )
                
                # Create a simple lookup from base name to full inventory name
                # e.g., "BUD LIGHT" -> "BEER BTL Bud Light"
                item_lookup = {item.split()[-1].upper(): item for item in simple_parse_items}

                sales_counts = {}
                for line in sales_mix_lines:
                    # Find a number at the end of the line
                    match = re.search(r'(\d+)$', line)
                    if match:
                        quantity = int(match.group(1))
                        # Find which item this line corresponds to
                        for base_name, full_name in item_lookup.items():
                            if base_name in line.upper():
                                sales_counts[full_name] = sales_counts.get(full_name, 0) + quantity
                                break # Stop searching once we find a match on this line

                # --- Variance Calculation ---
                variance_data = []
                latest_date = full_df['Date'].max()
                actual_usage_df = full_df[full_df['Date'] == latest_date][['Item', 'Usage']].set_index('Item')

                for item, qty_sold in sales_counts.items():
                    theoretical_usage = qty_sold
                    actual_usage = actual_usage_df.loc[item, 'Usage'] if item in actual_usage_df.index else 0
                    variance = actual_usage - theoretical_usage

                    variance_data.append({
                        "Item": item,
                        "Actual Usage": actual_usage,
                        "Theoretical Usage (Sold)": theoretical_usage,
                        "Variance": variance
                    })

                if variance_data:
                    variance_df = pd.DataFrame(variance_data)
                    def style_variance(val):
                        if abs(val) >= 2: return 'background-color: #ff4b4b' # Variance of 2+ units
                        elif abs(val) >= 1: return 'background-color: #ffb400'# Variance of 1+ unit
                        return ''

                    st.markdown("---")
                    st.dataframe(
                        variance_df.style.format({
                            "Actual Usage": "{:.1f}",
                            "Theoretical Usage (Sold)": "{:.0f}",
                            "Variance": "{:+.1f}"
                        }).applymap(style_variance, subset=['Variance']),
                        use_container_width=True, hide_index=True
                    )
                else:
                    st.warning("No matching items found between your sales mix and inventory. Please check item names.")

            except Exception as e:
                st.error(f"Could not process the Sales Mix file. The format may be unexpected. Error: {e}")
