import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Beverage Usage Analyzer", layout="wide")
st.title("🍺 Beverage Usage Analyzer")

uploaded_file = st.file_uploader("Upload BEVWEEKLY Excel File", type="xlsx")

if uploaded_file:
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
            df['Date'] = pd.to_datetime(xls.parse(sheet).iloc[1, 0], errors='coerce')
            compiled_data.append(df)
        except Exception as e:
            st.warning(f"Skipped {sheet}: {e}")
            continue

    full_df = pd.concat(compiled_data, ignore_index=True)
    full_df = full_df.dropna(subset=['Item', 'Usage'])
    full_df['Usage'] = pd.to_numeric(full_df['Usage'], errors='coerce')
    full_df['End Inventory'] = pd.to_numeric(full_df['End Inventory'], errors='coerce')
    full_df = full_df.dropna(subset=['Usage', 'End Inventory'])
    full_df = full_df.sort_values(by=['Item', 'Date'])

    def compute_metrics(group):
        group = group.sort_values(by='Date').reset_index(drop=True)
        usage = group['Usage']
        inventory = group['End Inventory']
        dates = group['Date']

        last_10 = usage[-10:]
        last_4 = usage[-4:]
        rolling_4 = usage.rolling(window=4)

        current_year = datetime.now().year
        ytd_usage = group[dates.dt.year == current_year]['Usage']
        ytd_avg = ytd_usage.mean() if not ytd_usage.empty else None

        def safe_div(n, d):
            return round(n / d, 2) if d and d > 0 else None

        return pd.Series({
            'End Inv': round(inventory.iloc[-1], 2),
            'YTD Avg': round(ytd_avg, 2) if ytd_avg is not None else None,
            '10Wk Avg': round(last_10.mean(), 2),
            '4Wk Avg': round(last_4.mean(), 2),
            'AT-High': round(usage.max(), 2),
            'Low4 Avg': round(rolling_4.mean().min(), 2) if len(usage) >= 4 else None,
            'High4 Avg': round(rolling_4.mean().max(), 2) if len(usage) >= 4 else None,
            'Wks Rmn (YTD Avg)': safe_div(inventory.iloc[-1], ytd_avg),
            'Wks Rmn (10Wk Avg)': safe_div(inventory.iloc[-1], last_10.mean()),
            'Wks Rmn (4Wk Avg)': safe_div(inventory.iloc[-1], last_4.mean()),
            'Wks Rmn (ATH)': safe_div(inventory.iloc[-1], usage.max()),
            'Wks Rmn (Low4Avg)': safe_div(inventory.iloc[-1], rolling_4.mean().min()),
            'Wks Rmn (High4 Avg)': safe_div(inventory.iloc[-1], rolling_4.mean().max())
        })

    summary_df = full_df.groupby('Item').apply(compute_metrics).reset_index()
    summary_df['Item'] = summary_df['Item'].astype(str)
    summary_df['ItemOrder'] = summary_df['Item'].apply(
        lambda x: original_order.index(x) if x in original_order else float('inf')
    )
    summary_df = summary_df.sort_values(by='ItemOrder').drop(columns='ItemOrder')

    tab_summary, tab_playground = st.tabs(["📊 Summary", "🧪 Playground"])

    with tab_summary:
        st.subheader("Usage Summary")
        threshold = st.slider("Highlight if weeks remaining is below:", min_value=1, max_value=10, value=2)

        def highlight_weeks_remaining(val, threshold=2):
            try:
                return 'background-color: red' if val < threshold else ''
            except:
                return ''

        format_dict = {
            col: '{:,.2f}' for col in summary_df.columns
            if summary_df[col].dtype in ['float64', 'float32']
        }

        styled_df = summary_df.style.format(format_dict).applymap(
            lambda val: highlight_weeks_remaining(val, threshold),
            subset=[
                'Wks Rmn (10Wk Avg)',
                'Wks Rmn (4Wk Avg)',
                'Wks Rmn (YTD Avg)',
                'Wks Rmn (ATH)',
                'Wks Rmn (Low4Avg)',
                'Wks Rmn (High4 Avg)'
            ]
        )

        st.dataframe(styled_df, use_container_width=True)

        csv = summary_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", data=csv, file_name="beverage_usage_summary.csv")

    with tab_playground:
        st.subheader("🧪 Playground: Inventory Planning")

        vendor_map_full = {
        "Breakthru": [
        "WHISKEY Crown Royal",
        "WHISKEY Crown Royal Regal Apple",
        "WHISKEY Jack Daniels Black",
        "WHISKEY Jack Daniels Tennessee Fire",
        "WHISKEY Bulleit Straight Rye",
        "WHISKEY Buffalo Trace",
        "WHISKEY Fireball Cinnamon",
        "VODKA Ketel One",
        "VODKA Deep Eddy Orange",
        "VODKA Deep Eddy Ruby Red",
        "VODKA Deep Eddy Lime",
        "LIQ Baileys Irish Cream",
        "LIQ Chambord",
        "LIQ Rumpleminze",
        "LIQ Amaretto",
        "LIQ Sour Apple",
        "LIQ Watermelon Schnapps",
        "LIQ Peach Schnapps",
        "LIQ Melon",
        "LIQ Triple Sec",
        "LIQ Butterscotch",
        "WELL Vodka",
        "WELL Rum",
        "WELL Gin",
        "WELL Tequila",
        "WELL Whiskey",
        "WELL Scotch",
        "WELL Brandy",
        "TEQUILA Don Julio Blanco",
        "TEQUILA Casamigos Blanco",
        "TEQUILA Corazon Reposado",
        "RUM Captain Morgan Spiced",
        "GIN Tanqueray",
        "WINE William Wycliff Brut Chateauamp",
        "WINE LaMarca Prosecco",
        "JUICE Red Bull",
        "JUICE Red Bull SF",
        "JUICE Red Bull Yellow",
        "BAR CONS Bloody Mary"
    ],
        "Southern": [
        "WHISKEY Basil Hayden",
        "WHISKEY Jameson",
        "WHISKEY Jim Beam",
        "WHISKEY Makers Mark",
        "WHISKEY Skrewball Peanut Butter",
        "VODKA Grey Goose",
        "VODKA Titos",
        "TEQUILA Cazadores Reposado",
        "TEQUILA Patron Silver",
        "WHISKEY Glenlivet",
        "WHISKEY Dewars White Label",
        "RUM Bacardi Superior White",
        "RUM Malibu Coconut",
        "LIQ Grand Marnier",
        "LIQ Hazelnut",  # Presumed full name if known, confirm if different
        "LIQ Jagermeister",
        "LIQ Kahlua",
        "LIQ Melon",
        "WINE Kendall Jackson Chardonnay",
        "WINE La Crema Chardonnay",
        "WINE La Crema Pinot Noir",
        "WINE Troublemaker Red",
        "WINE Villa Sandi Pinot Grigio",
        "BAR CONS Bitters",
        "BAR CONS Simple Syrup",
        "LIQ Vermouth Sweet",
        "LIQ Vermouth Dry"
    ],
        "Crescent": [
        "BEER DFT Alaskan Amber",
        "BEER DFT Blue Moon Belgian White",
        "BEER DFT Coors Light",
        "BEER DFT Dos Equis Lager",
        "BEER DFT New Belgium Juicy Haze IPA",
        "BEER DFT Miller Lite",
        "BEER DFT Modelo Especial",
        "BEER BTL Angry Orchard Crisp Apple",
        "BEER BTL Blue Moon",
        "BEER BTL Coors Light",
        "BEER BTL Corona Extra",
        "BEER BTL Corona NA",
        "BEER BTL Corona Premier",
        "BEER BTL Coronita Extra",
        "BEER BTL Dos Equis Lager",
        "BEER BTL Pacifico",
        "BEER BTL College Street Big Blue Van",
        "BEER BTL Guinness",
        "BEER BTL Heineken 0.0",
        "BEER BTL Truly Pineapple",
        "BEER BTL Truly Wild Berry",
        "BEER BTL Twisted Tea",
        "BEER BTL White Claw Black Cherry",
        "BEER BTL White Claw Mango",
        "BEER BTL White Claw Peach",
        "JUICE Ginger Beer",
        "VODKA Western Son Blueberry",
        "VODKA Western Son Lemon",
        "VODKA Western Son Original",
        "VODKA Western Son Prickly Pear",
        "VODKA Western Son Raspberry"
    ],
        "Hensley": [
        "BEER DFT Bud Light",
        "BEER DFT Michelob Ultra",
        "BEER DFT Firestone Walker 805",
        "BEER DFT Mother Road Tower Station",
        "BEER DFT Church Music",
        "BEER DFT Zipps Lager",
        "BEER BTL Austin Eastciders",
        "BEER BTL Budweiser",
        "BEER BTL Bud Light",
        "BEER BTL Michelob Ultra"
    ]
}

import ace_tools as tools; tools.display_dataframe_to_user(name="Vendor Item Mapping", dataframe=pd.DataFrame([(k, item) for k, v in vendor_map_full.items() for item in v], columns=["Vendor", "Item"]))
        category_map = {
            "Well": [], "Whiskey": [], "Vokda": [], "Gin": [], "Tequila": [], "Rum": [], "Scotch": [],
            "Liqueur": [], "Cordials": [], "Wine": [], "Draft Beer": [], "Bottled Beer": [], "Juice": []
        }
        for item in summary_df['Item']:
            upper_item = item.upper()
            if "WELL" in upper_item: category_map["Well"].append(item)
            elif "WHISKEY" in upper_item: category_map["Whiskey"].append(item)
            elif "VODKA" in upper_item: category_map["Vokda"].append(item)
            elif "GIN" in upper_item: category_map["Gin"].append(item)
            elif "TEQUILA" in upper_item: category_map["Tequila"].append(item)
            elif "RUM" in upper_item: category_map["Rum"].append(item)
            elif "SCOTCH" in upper_item: category_map["Scotch"].append(item)
            elif "LIQ " in upper_item and any(x in upper_item for x in ["AMARETTO", "BAILEYS", "CHAMBORD", "KAHLUA", "JAGER"]): category_map["Liqueur"].append(item)
            elif "LIQ " in upper_item or "SCHNAPPS" in upper_item: category_map["Cordials"].append(item)
            elif "WINE" in upper_item: category_map["Wine"].append(item)
            elif "BEER DFT" in upper_item: category_map["Draft Beer"].append(item)
            elif "BEER BTL" in upper_item: category_map["Bottled Beer"].append(item)
            elif "JUICE" in upper_item or "BAR CONS" in upper_item: category_map["Juice"].append(item)

        vendor_options = list(vendor_map.keys())
        selected_vendor = st.selectbox("Select Vendor", options=["All Vendors"] + vendor_options, index=0)

        base_items = summary_df['Item'].tolist() if selected_vendor == "All Vendors" else vendor_map[selected_vendor]

        category_options = list(category_map.keys())
        selected_categories = st.multiselect("Select Categories to Display", options=category_options, default=category_options)

        available_items = [item for cat in selected_categories for item in category_map[cat] if item in base_items]

        usage_option = st.radio("Select usage average for calculation:", ["YTD Avg", "10Wk Avg", "4Wk Avg"], index=0)

        editable_data = summary_df[summary_df['Item'].isin(available_items)][['Item', usage_option]].copy()
        editable_data['Add Bottles'] = 0.0
        editable_data['Desired Weeks'] = 0.0

        edited_df = st.data_editor(editable_data, num_rows="dynamic", use_container_width=True)

        if st.button("Calculate"):
            results = []
            for _, row in edited_df.iterrows():
                item = row['Item']
                avg = row[usage_option]
                bottles = row['Add Bottles']
                weeks = row['Desired Weeks']
                calc_weeks = bottles / avg if avg and bottles > 0 else 0
                calc_bottles = weeks * avg if avg and weeks > 0 else 0
                results.append({
                    'Item': item,
                    usage_option: avg,
                    'Add Bottles': bottles,
                    'Desired Weeks': weeks,
                    'Calc Weeks': round(calc_weeks, 2),
                    'Calc Bottles': round(calc_bottles, 2)
                })
            result_df = pd.DataFrame(results)
            st.dataframe(result_df, use_container_width=True)
