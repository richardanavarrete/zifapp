import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import openpyxl # Added for robust Excel manipulation

# --- Page Configuration ---
st.set_page_config(
    page_title="Bev Inventory System",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Mobile-Responsive CSS ---
# Using a more streamlined and modern style
st.markdown("""
<style>
    /* General App Styling */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        padding-left: 3rem;
        padding-right: 3rem;
    }
    /* Main Menu Buttons */
    .stButton>button {
        border-radius: 10px;
        padding: 1.25rem;
        font-size: 1.1rem;
        font-weight: bold;
        width: 100%;
        height: auto;
        border: 2px solid #764ba2;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.2);
        color: white;
        border-color: #667eea;
    }
    .stButton>button:disabled {
        background: #ced4da;
        color: #6c757d;
        border-color: #adb5bd;
    }
    /* Smaller Buttons */
    .stButton>button.small_btn {
        font-size: 1rem;
        padding: 0.5rem 1rem;
        font-weight: normal;
    }
</style>
""", unsafe_allow_html=True)


# --- Initialize Session State ---
def init_session_state():
    defaults = {
        'app_mode': 'menu',
        'bevweekly_data': None,
        'inventory_counts': {},
        'current_sheet_name': None,
        'uploaded_file_content': None,
        'scanned_barcode': None
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# --- Barcode Scanner Component ---
# This component now correctly communicates back to Streamlit
def barcode_scanner_component():
    """
    Creates a Streamlit component that wraps Quagga.js for barcode scanning.
    Returns the scanned code or None.
    """
    html_code = """
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/quagga/0.12.1/quagga.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/streamlit-component-lib@1.3.0/dist/streamlit-component-lib.js"></script>
        <style>
            #scanner-container {
                position: relative;
                width: 100%;
                height: 300px;
                border: 2px dashed #ccc;
                overflow: hidden;
                border-radius: 10px;
            }
            #scanner-container video { width: 100%; height: 100%; object-fit: cover; }
            .drawingBuffer { position: absolute; top: 0; left: 0; }
        </style>
    </head>
    <body>
        <div id="scanner-container"></div>
        <script>
            function sendValue(value) {
                Streamlit.setComponentValue(value);
            }

            Quagga.init({
                inputStream: {
                    name: "Live",
                    type: "LiveStream",
                    target: document.querySelector('#scanner-container'),
                    constraints: { width: 480, height: 320, facingMode: "environment" }
                },
                decoder: { readers: ["ean_reader", "code_128_reader", "upc_reader"] }
            }, function(err) {
                if (err) {
                    console.error(err);
                    document.getElementById('scanner-container').innerHTML = `<p style="color:red; text-align:center; padding-top: 50px;"><b>Camera Error:</b> ${err.message}</p>`;
                    return;
                }
                Quagga.start();
            });

            let lastScannedCode = null;
            let lastScannedTime = 0;

            Quagga.onDetected(function(result) {
                const code = result.codeResult.code;
                const now = new Date().getTime();
                // Debounce scans to avoid multiple triggers for the same item
                if (code !== lastScannedCode || (now - lastScannedTime > 5000)) { // 5-second cooldown
                    lastScannedCode = code;
                    lastScannedTime = now;
                    sendValue(code); // Send the detected code back to Streamlit
                }
            });
        </script>
    </body>
    </html>
    """
    scanned_code = st.components.v1.html(html_code, height=320)
    return scanned_code


# --- Data Processing Functions ---
@st.cache_data
def load_bevweekly_data(file_content):
    """Load and process the BevWeekly Excel file from file content bytes."""
    try:
        xls = pd.ExcelFile(BytesIO(file_content))
        sheet_names = xls.sheet_names

        # Get original item order from the first sheet
        df_first_sheet = xls.parse(sheet_names[0], skiprows=4)
        original_order = df_first_sheet.iloc[:, 0].dropna().astype(str).tolist()

        # Find the next week's sheet (first one with an empty "End Inventory" column)
        next_week_sheet = None
        for sheet in sheet_names:
            try:
                # Check for empty End Inventory (column index 7)
                df = xls.parse(sheet, skiprows=4)
                if len(df.columns) > 7 and (df.iloc[:, 7].isna().all() or (df.iloc[:, 7] == 0).all()):
                    next_week_sheet = sheet
                    break
            except Exception:
                continue
        
        # Default to the last sheet if no empty one is found
        if next_week_sheet is None:
            next_week_sheet = sheet_names[-1]

        # Get a map of Item Name -> Excel Row Number for easy updating later
        target_df = xls.parse(next_week_sheet, skiprows=4)
        item_to_row_map = {
            str(item).strip(): index + 5  # +5 to account for header rows (0-indexed + 4 skipped rows + 1 for 1-based Excel)
            for index, item in target_df.iloc[:, 0].dropna().items()
        }

        return {
            'sheet_names': sheet_names,
            'original_order': original_order,
            'next_week_sheet': next_week_sheet,
            'item_to_row_map': item_to_row_map
        }
    except Exception as e:
        st.error(f"❌ Error loading BevWeekly file: {e}")
        return None

# --- Main Application ---
def run_app():
    # --- HEADER AND NAVIGATION ---
    if st.session_state.app_mode != 'menu':
        col1, _, col2 = st.columns([1, 3, 1])
        with col1:
            if st.button("← Back to Menu"):
                st.session_state.app_mode = 'menu'
                st.rerun()
        with col2:
            st.markdown(
                f"<div style='text-align:right; padding-top:10px;'>File Loaded: "
                f"{'✅' if st.session_state.bevweekly_data else '⚠️ None'}</div>",
                unsafe_allow_html=True
            )

    # --- MENU MODE ---
    if st.session_state.app_mode == 'menu':
        st.title("🍺 Beverage Inventory System")
        st.markdown("---")

        st.subheader("📁 Upload BevWeekly File")
        uploaded_file = st.file_uploader(
            "Upload your BEVWEEKLY Excel File to begin.", type="xlsx", key="main_upload"
        )

        if uploaded_file:
            file_content = uploaded_file.getvalue()
            if st.session_state.uploaded_file_content != file_content:
                st.session_state.uploaded_file_content = file_content
                with st.spinner("Processing Excel file..."):
                    st.session_state.bevweekly_data = load_bevweekly_data(file_content)
                    st.session_state.inventory_counts = {} # Reset counts on new file upload

        if st.session_state.bevweekly_data:
            st.success(
                f"✅ File loaded successfully! Inventory will be updated on sheet: "
                f"**{st.session_state.bevweekly_data['next_week_sheet']}**"
            )
            item_count = len(st.session_state.bevweekly_data['original_order'])
            st.info(f"📦 Found **{item_count}** items to be inventoried.")

        st.markdown("---")
        st.subheader("Select an Action")
        col1, col2 = st.columns(2)
        file_loaded = st.session_state.bevweekly_data is not None

        with col1:
            if st.button("📱 Take Inventory", disabled=not file_loaded, help="Start counting items by scanning or manual entry."):
                st.session_state.app_mode = 'scanner'
                st.rerun()

        with col2:
            # Placeholder for Analysis & Reports functionality
            if st.button("📊 Analysis & Reports (Coming Soon)", disabled=True):
                # st.session_state.app_mode = 'analysis'
                # st.rerun()
                pass


    # --- SCANNER / INVENTORY MODE ---
    elif st.session_state.app_mode == 'scanner':
        st.title("📱 Take Inventory")

        if not st.session_state.bevweekly_data:
            st.error("Please go back to the menu and upload a BevWeekly file first.")
            return

        # --- PROGRESS BAR ---
        total_items = len(st.session_state.bevweekly_data['original_order'])
        counted_items = len(st.session_state.inventory_counts)
        progress = counted_items / total_items if total_items > 0 else 0
        
        st.progress(progress, text=f"{counted_items} / {total_items} Items Counted ({progress:.0%})")
        st.markdown("---")

        col1, col2 = st.columns(2)

        # --- LEFT COLUMN: SCANNER AND MANUAL ENTRY ---
        with col1:
            st.subheader("📷 Scan or Search")
            
            # Barcode scanner
            scanned_code = barcode_scanner_component()
            if scanned_code:
                st.session_state.scanned_barcode = scanned_code
                # In a real app with a barcode map, you'd find the item name here.
                # For now, we'll just show the code and pre-fill the search.
                st.success(f"Barcode Scanned: `{st.session_state.scanned_barcode}`")

            # Item search and selection
            items_list = st.session_state.bevweekly_data['original_order']
            search_query = st.text_input(
                "Search for an item",
                placeholder="e.g., 'Bulleit' or 'Coors'",
                # Use scanned code as default search term if available
                value=st.session_state.scanned_barcode or "" 
            )

            if search_query:
                filtered_items = [item for item in items_list if search_query.lower() in item.lower()]
                if not filtered_items:
                    st.warning("No items match your search.")
            else:
                # Show uncounted items first
                uncounted_items = [item for item in items_list if item not in st.session_state.inventory_counts]
                filtered_items = uncounted_items[:15] # Limit initial display
            
            selected_item = st.selectbox(
                "Select Item to Count:",
                filtered_items,
                index=0 if filtered_items else None,
                help="Items you have already counted will not appear here unless you search for them."
            )
            
            if selected_item:
                current_count = st.session_state.inventory_counts.get(selected_item, 0.0)
                
                # Input form for the selected item
                with st.form(key=f"form_{selected_item}", clear_on_submit=True):
                    new_count = st.number_input(
                        f"Enter count for **{selected_item}**:",
                        min_value=0.0,
                        value=float(current_count),
                        step=0.5
                    )
                    submitted = st.form_submit_button("Update Count", use_container_width=True)
                    if submitted:
                        st.session_state.inventory_counts[selected_item] = new_count
                        st.session_state.scanned_barcode = None # Clear search after update
                        st.success(f"Updated '{selected_item}' to {new_count}")
                        st.rerun()


        # --- RIGHT COLUMN: CURRENT INVENTORY & EXPORT ---
        with col2:
            st.subheader("📋 Current Inventory Session")

            if not st.session_state.inventory_counts:
                st.info("No items have been counted yet. Use the scanner or search on the left to begin.")
            else:
                # Create DataFrame for display and editing
                inventory_list = sorted(st.session_state.inventory_counts.items(), key=lambda x: items_list.index(x[0]))
                inventory_df = pd.DataFrame(inventory_list, columns=["Item", "Count"])

                edited_df = st.data_editor(
                    inventory_df,
                    hide_index=True,
                    use_container_width=True,
                    num_rows="dynamic",
                    column_config={
                        "Item": st.column_config.TextColumn(disabled=True),
                        "Count": st.column_config.NumberColumn(label="Count", min_value=0, step=0.5, required=True)
                    },
                    key="data_editor"
                )

                # Update session state if edits were made in the data_editor
                if not edited_df.equals(inventory_df):
                    st.session_state.inventory_counts = dict(zip(edited_df['Item'], edited_df['Count']))
                    st.toast("Changes saved!")
                    st.rerun()

                st.markdown("---")
                
                btn_col1, btn_col2 = st.columns(2)
                
                with btn_col1:
                    # FIX: Correctly call .clear() on the dictionary
                    if st.button("🗑️ Clear All Counts", use_container_width=True, type="secondary"):
                        st.session_state.inventory_counts.clear()
                        st.rerun()
                
                with btn_col2:
                    # FIX: Use openpyxl for a safe, format-preserving export
                    if st.download_button(
                        label="💾 Download Updated File",
                        data=export_updated_excel(),
                        file_name=f"Updated_BEVWEEKLY_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        type="primary",
                        disabled=not st.session_state.inventory_counts
                    ):
                        st.success("✅ Export successful!")


# --- EXPORT FUNCTION (REWRITTEN) ---
def export_updated_excel():
    """
    Surgically updates the target Excel sheet with new inventory counts
    using openpyxl to preserve all original formatting.
    """
    if not st.session_state.bevweekly_data or not st.session_state.inventory_counts:
        return None

    try:
        # Load the original uploaded file content into an openpyxl workbook object
        file_stream = BytesIO(st.session_state.uploaded_file_content)
        workbook = openpyxl.load_workbook(file_stream)

        # Get the specific sheet to update
        target_sheet_name = st.session_state.bevweekly_data['next_week_sheet']
        sheet = workbook[target_sheet_name]

        # Get the map of item names to their corresponding row numbers
        item_to_row_map = st.session_state.bevweekly_data['item_to_row_map']
        
        # Iterate through the counted items and update the cells
        # Column H is the 8th column, which corresponds to "End Inventory"
        END_INVENTORY_COL = 8
        for item, count in st.session_state.inventory_counts.items():
            item_clean = item.strip()
            if item_clean in item_to_row_map:
                row_number = item_to_row_map[item_clean]
                sheet.cell(row=row_number, column=END_INVENTORY_COL, value=float(count))

        # Save the updated workbook to a new in-memory byte stream
        output_stream = BytesIO()
        workbook.save(output_stream)
        output_stream.seek(0) # Rewind the stream to the beginning
        
        return output_stream.getvalue()

    except Exception as e:
        st.error(f"Error during Excel export: {e}")
        return None


if __name__ == "__main__":
    run_app()
