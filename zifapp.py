import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO, StringIO
import openpyxl

# --- Page Configuration ---
st.set_page_config(
    page_title="Bev Inventory System V3",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Custom CSS for a cleaner look ---
st.markdown("""
<style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        padding-left: 2rem;
        padding-right: 2rem;
    }
    .stButton>button {
        border-radius: 10px;
        font-weight: bold;
        width: 100%;
    }
    .stAlert {
        border-radius: 10px;
    }
    .stTextInput input, .stNumberInput input {
        border-radius: 8px;
    }
    .card {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #dee2e6;
        margin-bottom: 1rem;
    }
    h1, h2, h3 {
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)


# --- Initialize Session State ---
def init_session_state():
    """Initializes all necessary session state variables."""
    defaults = {
        'app_mode': 'menu',
        'bevweekly_data': None,
        'inventory_counts': {},
        'uploaded_bevweekly_content': None,
        'sku_data': None, # This will hold the SKU -> Item mapping DataFrame
        'uploaded_sku_content': None,
        'item_to_count': None, # The specific item currently being counted
        'last_scanned_code': None, # The last barcode entered by the user
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# --- Data Processing Functions ---
@st.cache_data
def load_bevweekly_data(file_content):
    """Load and process the BevWeekly Excel file from bytes."""
    try:
        xls = pd.ExcelFile(BytesIO(file_content))
        sheet_names = xls.sheet_names
        # Assume the first sheet contains the master item list in the first column
        df_first_sheet = xls.parse(sheet_names[0], skiprows=4)
        # Get a clean list of all items in their original order
        original_order = df_first_sheet.iloc[:, 0].dropna().astype(str).tolist()

        # Find the target sheet for writing inventory (first one with an empty/zeroed 8th column)
        next_week_sheet = None
        for sheet in sheet_names:
            try:
                df = xls.parse(sheet, skiprows=4)
                # Column H is the 8th column (index 7)
                if len(df.columns) > 7 and (df.iloc[:, 7].isna().all() or (df.iloc[:, 7] == 0).all()):
                    next_week_sheet = sheet
                    break
            except Exception:
                continue
        # If no such sheet is found, default to the last one
        if next_week_sheet is None:
            next_week_sheet = sheet_names[-1]

        target_df = xls.parse(next_week_sheet, skiprows=4)
        item_to_row_map = {
            str(item).strip(): index + 5  # +5 to account for header rows and 0-indexing
            for index, item in target_df.iloc[:, 0].dropna().items()
        }

        return {
            'sheet_names': sheet_names,
            'original_order': original_order,
            'next_week_sheet': next_week_sheet,
            'item_to_row_map': item_to_row_map
        }
    except Exception as e:
        st.error(f"❌ **Error loading BevWeekly file:** {e}")
        return None

@st.cache_data
def load_sku_data(file_content):
    """Load the SKU database from uploaded CSV file content."""
    try:
        df = pd.read_csv(BytesIO(file_content))
        if 'Barcode' not in df.columns or 'Item' not in df.columns:
            st.error("❌ SKU Database must have 'Barcode' and 'Item' columns.")
            return None
        # Ensure barcode is treated as a string to avoid scientific notation
        df['Barcode'] = df['Barcode'].astype(str)
        return df
    except Exception as e:
        st.error(f"❌ **Error loading SKU Database:** {e}")
        return None

# --- Main Application Logic ---
def run_app():
    """Controls the main flow and UI of the Streamlit application."""

    # --- Header and Navigation ---
    if st.session_state.app_mode != 'menu':
        if st.button("⬅️ Back to Main Menu"):
            # Reset temporary states when going back to menu
            st.session_state.item_to_count = None
            st.session_state.last_scanned_code = None
            st.session_state.app_mode = 'menu'
            st.rerun()

    # --- Page 1: Main Menu & File Upload ---
    if st.session_state.app_mode == 'menu':
        st.title("🍺 Beverage Inventory System V3")
        st.markdown("A streamlined system for tracking inventory by linking SKUs to products.")
        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                st.subheader("Step 1: Upload Inventory Sheet")
                bevweekly_file = st.file_uploader("Upload your BEVWEEKLY Excel File", type="xlsx", key="bevweekly_uploader")
                if bevweekly_file:
                    file_content = bevweekly_file.getvalue()
                    if st.session_state.uploaded_bevweekly_content != file_content:
                        st.session_state.uploaded_bevweekly_content = file_content
                        st.session_state.bevweekly_data = load_bevweekly_data(file_content)
                        st.session_state.inventory_counts = {} # Reset counts on new file

        with col2:
            with st.container(border=True):
                st.subheader("Step 2: Upload SKU Database")
                sku_file = st.file_uploader("Upload your SKU Database (sku_db.csv)", type="csv", key="sku_uploader")
                if sku_file:
                    file_content = sku_file.getvalue()
                    if st.session_state.uploaded_sku_content != file_content:
                        st.session_state.uploaded_sku_content = file_content
                        st.session_state.sku_data = load_sku_data(file_content)
                elif st.session_state.sku_data is None:
                    st.info("No SKU file uploaded. A new database will be created during this session.")
                    st.session_state.sku_data = pd.DataFrame(columns=['Barcode', 'Item'])


        st.markdown("---")
        if st.session_state.bevweekly_data:
            st.success(f"✅ BevWeekly file loaded. Inventory will be saved to sheet: **{st.session_state.bevweekly_data['next_week_sheet']}**")
            st.success(f"✅ SKU Database loaded with **{len(st.session_state.sku_data)}** known products.")
            if st.button("🚀 Start Inventory Session", type="primary"):
                st.session_state.app_mode = 'inventory'
                st.rerun()
        else:
            st.warning("Please upload a BevWeekly file to begin.")

    # --- Page 2: Inventory Counting ---
    elif st.session_state.app_mode == 'inventory':
        st.title("📱 Take Inventory")

        col1, col2 = st.columns([0.6, 0.4])

        with col1:
            st.subheader("🔍 Find Item")
            st.markdown('<div class="card">', unsafe_allow_html=True)

            # --- Barcode Input & Lookup ---
            barcode = st.text_input("Enter or Scan Barcode", key="barcode_input", placeholder="Scan a barcode here...")
            if barcode and barcode != st.session_state.get('last_scanned_code'):
                st.session_state.last_scanned_code = barcode
                known_item = st.session_state.sku_data[st.session_state.sku_data['Barcode'] == barcode]
                if not known_item.empty:
                    item_name = known_item['Item'].iloc[0]
                    st.session_state.item_to_count = item_name
                    st.toast(f"✅ Found: {item_name}", icon="👍")
                else:
                    st.session_state.item_to_count = None # Clear previous item if new barcode is unknown
                    st.toast(f"❓ New barcode detected!", icon="🧐")

            # --- Learning System for New Barcodes ---
            if st.session_state.last_scanned_code and st.session_state.item_to_count is None:
                with st.container(border=True):
                    st.warning(f"**New Barcode:** `{st.session_state.last_scanned_code}`")
                    st.write("This barcode isn't in your database. Please link it to an item.")
                    all_items = st.session_state.bevweekly_data['original_order']
                    item_to_link = st.selectbox("Select the correct item for this barcode:", all_items, index=None, placeholder="Search and select item...")
                    if st.button("🔗 Link Barcode to Item"):
                        if item_to_link:
                            new_entry = pd.DataFrame([{'Barcode': st.session_state.last_scanned_code, 'Item': item_to_link}])
                            st.session_state.sku_data = pd.concat([st.session_state.sku_data, new_entry], ignore_index=True)
                            st.session_state.item_to_count = item_to_link
                            st.success(f"Linked `{st.session_state.last_scanned_code}` to `{item_to_link}`")
                            st.rerun() # Refresh the state to show the counting form

            # --- Manual Search as Fallback ---
            st.markdown("<p style='text-align:center; font-weight:bold;'>OR</p>", unsafe_allow_html=True)
            manual_item_select = st.selectbox(
                "Manually search and select an item",
                st.session_state.bevweekly_data['original_order'],
                index=None if not st.session_state.item_to_count else st.session_state.bevweekly_data['original_order'].index(st.session_state.item_to_count),
                placeholder="Select an item to count..."
            )
            if manual_item_select and manual_item_select != st.session_state.item_to_count:
                st.session_state.item_to_count = manual_item_select
                st.session_state.last_scanned_code = None # Clear barcode if manually selecting

            st.markdown('</div>', unsafe_allow_html=True)

            # --- Counting Form ---
            if st.session_state.item_to_count:
                st.subheader("🔢 Add Counts")
                st.markdown('<div class="card">', unsafe_allow_html=True)
                item = st.session_state.item_to_count
                current_counts = st.session_state.inventory_counts.get(item, [])
                total_so_far = sum(current_counts)

                st.write(f"#### Counting: **{item}**")
                if total_so_far > 0:
                    st.info(f"Current Total: **{total_so_far}** (Counts: `{current_counts}`)")

                with st.form(key=f"count_form_{item}", clear_on_submit=True):
                    new_count = st.number_input("Add to count:", min_value=0.0, step=0.5)
                    submitted = st.form_submit_button("Add Count", type="primary")
                    if submitted and new_count > 0:
                        st.session_state.inventory_counts.setdefault(item, []).append(new_count)
                        st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)


        with col2:
            st.subheader("📋 Session Summary")
            st.markdown('<div class="card" style="min-height: 500px;">', unsafe_allow_html=True)
            if not st.session_state.inventory_counts:
                st.info("Counted items will appear here.")
            else:
                counted_data = []
                # Display in the order from the original Excel file
                for item in st.session_state.bevweekly_data['original_order']:
                    if item in st.session_state.inventory_counts:
                         counts = st.session_state.inventory_counts[item]
                         counted_data.append({
                             "Item": item,
                             "Total Count": sum(counts),
                             "Entries": str(counts)
                         })
                display_df = pd.DataFrame(counted_data)
                st.dataframe(display_df, hide_index=True, use_container_width=True)

            # --- Export Section ---
            st.markdown("---")
            st.subheader("💾 Export Results")
            
            # --- FIX: Only generate Excel and show button if there are counts ---
            if st.session_state.inventory_counts:
                excel_data = export_updated_excel()
                # Check if export was successful before showing button
                if excel_data:
                    st.download_button(
                        label="Download Updated Inventory",
                        data=excel_data,
                        file_name=f"Updated_BEVWEEKLY_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
            else:
                st.info("Your inventory download link will appear here once you count an item.")


            # Download Updated SKU Database - This should always be available
            # in case the user only linked new SKUs without counting.
            if st.session_state.sku_data is not None and not st.session_state.sku_data.empty:
                csv_data = st.session_state.sku_data.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Updated SKU Database",
                    data=csv_data,
                    file_name="sku_db.csv",
                    mime="text/csv",
                    help="Save this file and re-upload it next time you do inventory."
                )

            st.markdown('</div>', unsafe_allow_html=True)


def export_updated_excel():
    """Updates the Excel file in memory and returns it as bytes for download."""
    if not st.session_state.bevweekly_data or not st.session_state.inventory_counts:
        return None
    try:
        file_stream = BytesIO(st.session_state.uploaded_bevweekly_content)
        workbook = openpyxl.load_workbook(file_stream)
        sheet = workbook[st.session_state.bevweekly_data['next_week_sheet']]
        item_map = st.session_state.bevweekly_data['item_to_row_map']

        # Column H is the End Inventory column
        END_INVENTORY_COL_INDEX = 8

        for item, counts in st.session_state.inventory_counts.items():
            total = sum(counts)
            if item.strip() in item_map:
                row = item_map[item.strip()]
                sheet.cell(row=row, column=END_INVENTORY_COL_INDEX, value=float(total))

        output_stream = BytesIO()
        workbook.save(output_stream)
        output_stream.seek(0)
        return output_stream.getvalue()

    except Exception as e:
        st.error(f"Excel Export Error: {e}")
        return None

if __name__ == "__main__":
    init_session_state()
    run_app()