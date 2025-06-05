import streamlit as st
import pandas as pd

st.title("Beverage Usage Analyzer")

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
        last_10 = usage[-10:]
        last_4 = usage[-4:]
        rolling_4 = usage.rolling(window=4)

        def safe_div(n, d):
            return round(n / d, 2) if d and d > 0 else None

        return pd.Series({
            'End Inv': round(inventory.iloc[-1], 2),
            '10Wk Avg': round(last_10.mean(), 2),
            '4Wk Avg': round(last_4.mean(), 2),
            'AT-High': round(usage.max(), 2),
            'Low 4Wk Avg': round(rolling_4.mean().min(), 2) if len(usage) >= 4 else None,
            'High 4Wk Avg': round(rolling_4.mean().max(), 2) if len(usage) >= 4 else None,
            'Wks Rmn (10-Week Avg)': safe_div(inventory.iloc[-1], last_10.mean()),
            'Wks Rmn (Last 4-Week Avg)': safe_div(inventory.iloc[-1], last_4.mean()),
            'Wks Rmn (All-Time High)': safe_div(inventory.iloc[-1], usage.max()),
            'Wks Rmn (Lowest 4-Week Avg)': safe_div(inventory.iloc[-1], rolling_4.mean().min()),
            'Wks Rmn (Highest 4-Week Avg)': safe_div(inventory.iloc[-1], rolling_4.mean().max())
        })

    summary_df = full_df.groupby('Item').apply(compute_metrics).reset_index()

    summary_df['Item'] = summary_df['Item'].astype(str)
    summary_df['ItemOrder'] = summary_df['Item'].apply(
        lambda x: original_order.index(x) if x in original_order else float('inf')
    )
    summary_df = summary_df.sort_values(by='ItemOrder').drop(columns='ItemOrder')

    st.subheader("Usage Summary")
    st.dataframe(summary_df.reset_index(drop=True), use_container_width=True)

    csv = summary_df.to_csv(index=False).encode('utf-8')
    st.download_button("Download CSV", data=csv, file_name="beverage_usage_summary.csv")
