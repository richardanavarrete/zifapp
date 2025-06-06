import streamlit as st
import pandas as pd
from datetime import datetime

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

    with tab_sales_analysis:
        st.subheader("Sales vs. Actual Usage Variance")
        st.markdown("This tool analyzes the difference between items sold (from your POS) and items used (from your inventory count).")
        
        # --- Configuration moved inside an expander ---
        with st.expander("Click to view and edit Sales Mix Configuration"):
            st.markdown("##### 1. Pour & Container Volumes (in ounces)")
            st.warning("These values must be accurate for calculations to be correct.")
            VOLUME_CONFIG = {
                "16oz": 16, "32oz": 32, "Pitcher": 64, "Liquor Pour": 1.5, "Wine Pour": 6,
                "Half Barrel Keg": 1984, "Sixtel Keg": 661,
                "Standard Liquor/Wine Bottle": 25.4, "Liter Liquor Bottle": 33.8,
            }
            st.json(VOLUME_CONFIG)

            st.markdown("##### 2. Inventory Item to Container Mapping")
            st.warning("You must map every DRAFT and LIQUOR/WINE item you want to analyze to its container size.")
            ITEM_CONTAINER_MAP = {
                "BEER DFT Alaskan Amber": "Half Barrel Keg", "WHISKEY Buffalo Trace": "Standard Liquor/Wine Bottle",
                # Add all other draft, liquor, and wine items here...
            }
            st.json(ITEM_CONTAINER_MAP)

        sales_mix_file = st.file_uploader("Upload Weekly Sales Mix Excel File", type=["xlsx", "csv"])

        if sales_mix_file:
            try:
                sales_df = pd.read_excel(sales_mix_file) if sales_mix_file.name.endswith('xlsx') else pd.read_csv(sales_mix_file)
                sales_df.columns = [col.strip() for col in sales_df.columns]
                
                st.markdown("---")
                st.markdown("#### Please confirm your column names:")
                
                # --- NEW: User selects which columns to use ---
                col1, col2 = st.columns(2)
                with col1:
                    item_col = st.selectbox("Which column contains the ITEM NAMES?", sales_df.columns)
                with col2:
                    qty_col = st.selectbox("Which column contains the QUANTITY SOLD?", sales_df.columns)

                total_volume_sold_by_item = {}
                all_inventory_items = list(summary_df['Item'].unique())

                def get_inventory_item_and_pour_oz(sales_name):
                    sales_name_upper = sales_name.upper()
                    # Check for exact match first (bottled beer, simple liquors/wines)
                    if sales_name in all_inventory_items:
                        if "BEER BTL" in sales_name_upper: return sales_name, 1, 'count'
                        if "WINE" in sales_name_upper: return sales_name, VOLUME_CONFIG["Wine Pour"], 'volume'
                        return sales_name, VOLUME_CONFIG["Liquor Pour"], 'volume'
                    # Check for keyword match (draft beer)
                    for keyword in ["16oz", "32oz", "Pitcher"]:
                        if sales_name_upper.startswith(keyword.upper()):
                            base_name = sales_name[len(keyword):].strip().upper()
                            for inv_item in all_inventory_items:
                                if base_name in inv_item.upper() and "BEER DFT" in inv_item.upper():
                                    return inv_item, VOLUME_CONFIG.get(keyword), 'volume'
                    # Final check for partial match (e.g. "Buffalo Trace" in sales -> "WHISKEY Buffalo Trace")
                    for inv_item in all_inventory_items:
                        if sales_name_upper in inv_item.upper():
                           if "WINE" in inv_item.upper(): return inv_item, VOLUME_CONFIG["Wine Pour"], 'volume'
                           return inv_item, VOLUME_CONFIG["Liquor Pour"], 'volume'
                    return None, None, None

                for _, row in sales_df.iterrows():
                    sales_item_name = row[item_col]
                    qty_sold = row[qty_col]
                    if pd.isna(sales_item_name) or pd.isna(qty_sold): continue
                    
                    inv_item, pour_value, sale_type = get_inventory_item_and_pour_oz(sales_item_name)

                    if inv_item:
                        current_total = total_volume_sold_by_item.get(inv_item, {'type': sale_type, 'total': 0})
                        current_total['total'] += qty_sold * pour_value
                        total_volume_sold_by_item[inv_item] = current_total

                variance_data = []
                latest_date = full_df['Date'].max()
                actual_usage_df = full_df[full_df['Date'] == latest_date][['Item', 'Usage']].set_index('Item')

                for item, data in total_volume_sold_by_item.items():
                    total_sold, sale_type = data['total'], data['type']
                    actual_usage = actual_usage_df.loc[item, 'Usage'] if item in actual_usage_df.index else 0
                    unit, theoretical_usage, variance = "units", 0, 0
                    
                    if sale_type == 'volume':
                        container_key = ITEM_CONTAINER_MAP.get(item)
                        if not container_key: continue
                        total_container_volume = VOLUME_CONFIG.get(container_key)
                        if not total_container_volume or total_container_volume == 0: continue
                        theoretical_usage = total_sold / total_container_volume
                        unit = "% of container"
                        variance = actual_usage - theoretical_usage
                    else: # 'count' type for bottled beer
                        theoretical_usage = total_sold
                        unit = "bottles"
                        variance = actual_usage - theoretical_usage

                    variance_data.append({
                        "Item": item, "Actual Usage": actual_usage,
                        "Theoretical Usage": theoretical_usage, "Variance": variance, "Unit": unit
                    })

                if variance_data:
                    variance_df = pd.DataFrame(variance_data)
                    def style_variance(row):
                        color = ''
                        if row['Unit'] == 'bottles' and abs(row['Variance']) >= 2: color = 'background-color: #ff4b4b'
                        elif row['Unit'] == 'bottles' and abs(row['Variance']) >= 1: color = 'background-color: #ffb400'
                        elif row['Unit'] == '% of container' and abs(row['Variance']) >= 0.10: color = 'background-color: #ff4b4b'
                        elif row['Unit'] == '% of container' and abs(row['Variance']) >= 0.05: color = 'background-color: #ffb400'
                        return [color] * len(row)

                    st.markdown("---")
                    st.dataframe(
                        variance_df.style.format({
                            "Actual Usage": "{:.2f}", "Theoretical Usage": "{:.2f}", "Variance": "{:+.2f}"
                        }).apply(style_variance, axis=1),
                        use_container_width=True, hide_index=True
                    )
            except Exception as e:
                st.error(f"Could not process the Sales Mix file. Please check the file format and selected columns. Error: {e}")
