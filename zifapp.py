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
                    df['Date'] = pd.NaT # Use NaT for proper datetime handling
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
        
        # Logic for Highest 4: Average of the 4 largest values overall
        avg_of_highest_4 = usage.nlargest(4).mean() if not usage.empty else None

        # Logic for Lowest 4: Filter out zeros, then find the average of the 4 smallest non-zero values
        non_zero_usage = usage[usage > 0]
        avg_of_lowest_4_non_zero = non_zero_usage.nsmallest(4).mean() if not non_zero_usage.empty else None

        return pd.Series({
            'End Inv': round(inventory.iloc[-1], 2),
            'YTD Avg': round(ytd_avg, 2) if pd.notna(ytd_avg) else None,
            '10Wk Avg': round(last_10.mean(), 2) if not last_10.empty else None,
            '4Wk Avg': round(last_4.mean(), 2) if not last_4.empty else None,
            'AT-High': round(usage.max(), 2),
            '4WkLow Avg (Ø)': round(avg_of_lowest_4_non_zero, 2) if pd.notna(avg_of_lowest_4_non_zero) else None,
            '4WkHigh Avg': round(avg_of_highest_4, 2) if pd.notna(avg_of_highest_4) else None,
            'WksRmn(10Wk)': safe_div(inventory.iloc[-1], last_10.mean()),
            'WksRmn(4Wk)': safe_div(inventory.iloc[-1], last_4.mean()),
            'WksRmn(YTD)': safe_div(inventory.iloc[-1], ytd_avg),
            'WksRmn(ATH)': safe_div(inventory.iloc[-1], usage.max()),
            'WksRmn(Lo4)': safe_div(inventory.iloc[-1], avg_of_lowest_4_non_zero),
            'WksRmn(Hi
