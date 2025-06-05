import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Beverage Usage Analyzer", layout="wide")
st.title("🍺 Beverage Usage Analyzer")

uploaded_file = st.file_uploader("Upload BEVWEEKLY Excel File", type="xlsx")

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    sheet_names = xls.sheet_names

    # Get original item order from first sheet
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

    st.subheader("Usage Summary")

    # Add a dynamic threshold slider
    threshold = st.slider("Highlight if weeks remaining is below:", min_value=1, max_value=10, value=2)

    # Define styling function
    def highlight_weeks_remaining(val, threshold=2):
        try:
            return 'background-color: red' if val < threshold else ''
        except:
            return ''

    # Apply style to specific columns
    styled_df = summary_df.style.applymap(
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

    # Display with styling
    st.dataframe(styled_df, use_container_width=True)

    # Download option
    csv = summary_df.to_csv(index=False).encode('utf-8')
    st.download_button("Download CSV", data=csv, file_name="beverage_usage_summary.csv")
