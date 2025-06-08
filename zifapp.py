import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import openpyxl

# --- Page Configuration ---
st.set_page_config(
    page_title="Bev Inventory System",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Mobile-Responsive CSS ---
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
        padding: 1rem;
        font-weight: bold;
    }
    .stAlert {
        border-radius: 10px;
    }
    .stTextInput input, .stNumberInput input {
        border-radius: 8px;
    }
    .inventory-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #dee2e6;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)


# --- Initialize Session State ---
def init_session_state():
    """Initializes session state variables if they don't exist."""
    defaults = {
        'app_mode': 'menu',
        'bevweekly_data': None,
        # IMPORTANT: inventory_counts is now a dict of lists for accumulative counting
        'inventory_counts': {},
        'uploaded_file_content': None,
        'scanned_barcode': None
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# --- Barcode Scanner Component (V2 with Visual Feedback) ---
def barcode_scanner_component():
    """
    Creates a Streamlit component that wraps Quagga.js for barcode scanning.
    Includes live visual feedback (green box around detected codes).
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
            #scanner-container video, #scanner-container canvas {
                width: 100%;
                height: 100%;
                position: absolute;
                top: 0;
                left: 0;
            }
            #scanner-container canvas.drawingBuffer {
                z-index: 10;
            }
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
                locator: { patchSize: "medium", halfSample: true },
                numOfWorkers: 2,
                frequency: 10,
                decoder: {
                    readers: [
                        "code_128_reader", "ean_reader", "ean_8_reader",
                        "code_39_reader", "upc_reader", "i2of5_reader"
                    ]
                },
                locate: true
            }, function(err) {
                if (err) {
                    console.error(err);
                    document.getElementById('scanner-container').innerHTML = `<p style="color:red; text-align:center; padding-top: 50px;"><b>Camera Error:</b> ${err.message}</p>`;
                    return;
                }
                Quagga.start();
            });

            Quagga.onProcessed(function(result) {
                var drawingCtx = Quagga.canvas.ctx.overlay,
                    drawingCanvas = Quagga.canvas.dom.overlay;
                if (result) {
                    if (result.boxes) {
                        drawingCtx.clearRect(0, 0, parseInt(drawingCanvas.getAttribute("width")), parseInt(drawingCanvas.getAttribute("height")));
                        result.boxes.filter(function (box) {
                            return box !== result.box;
                        }).forEach(function (box) {
                            Quagga.ImageDebug.drawPath(box, {x: 0, y: 1}, drawingCtx, {color: "green", lineWidth: 2});
                        });
                    }
                    if (result.box) {
                        Quagga.ImageDebug.drawPath(result.box, {x: 0, y: 1}, drawingCtx, {color: "#00F", lineWidth: 2});
                    }
                    if (result.codeResult && result.codeResult.code) {
                        Quagga.ImageDebug.drawPath(result.line, {x: 'x', y: 'y'}, drawingCtx, {color: 'red', lineWidth: 3});
                    }
                }
            });

            let lastScannedCode = null;
            let lastScannedTime = 0;

            Quagga.onDetected(function(result) {
                const code = result.codeResult.code;
                const now = new Date().getTime();
                if (code && (now - lastScannedTime > 3000)) { // 3-second cooldown
                    lastScannedTime = now;
                    sendValue(code); // Send the detected code back to Streamlit
                }
            });
        </script>
    </body>
    </html>
    """
    scanned_code = st.components.v1.html(html_code, height=320, scrolling=False)
    return scanned_code


# --- Data Processing Functions ---
@st.cache_data
def load_bevweekly_data(file_content):
    """Load and process the BevWeekly Excel file from file content bytes."""
    try:
        xls = pd.ExcelFile(BytesIO(file_content))
        sheet_names = xls.sheet_names
        df_first_sheet = xls.parse(sheet_names[0], skiprows=4)
        original_order = df_first_sheet.iloc[:, 0].dropna().astype(str).tolist()

        next_week_sheet = None
        for sheet in sheet_names:
            try:
                df = xls.parse(sheet, skiprows=4)
                if len(df.columns) > 7 and (df.iloc[:, 7].isna().all() or (df.iloc[:, 7] == 0).all()):
                    next_week_sheet = sheet
                    break
            except Exception:
                continue

        if next_week_sheet is None:
            next_week_sheet = sheet_names[-1]

        target_df = xls.parse(next_week_sheet, skiprows=4)
        item_to_row_map = {
            str(item).strip(): index + 5
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

# --- Main Application Logic ---
def run_app():
    if st.session_state.app_mode != 'menu':
        col1, _, col2 = st.columns([1, 3, 1])
        with col1:
            if st.button("⬅️ Menu"):
                st.session_state.app_mode = 'menu'
                st.rerun()
        with col2:
            st.markdown(
                f"<div style='text-align:right; padding-top:10px;'>File Loaded: "
                f"{'✅' if st.session_state.bevweekly_data else '⚠️'}</div>",
                unsafe_allow_html=True
            )

    if st.session_state.app_mode == 'menu':
        st.title("🍺 Beverage Inventory System")
        st.markdown("---")

        st.subheader("📁 Upload BevWeekly File")
        uploaded_file = st.file_uploader("Upload your BEVWEEKLY Excel File to begin.", type="xlsx")

        if uploaded_file:
            file_content = uploaded_file.getvalue()
            if st.session_state.uploaded_file_content != file_content:
                st.session_state.uploaded_file_content = file_content
                with st.spinner("Processing Excel file..."):
                    st.session_state.bevweekly_data = load_bevweekly_data(file_content)
                    st.session_state.inventory_counts = {}

        if st.session_state.bevweekly_data:
            st.success(f"✅ File loaded! Inventory will update sheet: **{st.session_state.bevweekly_data['next_week_sheet']}**")

        st.markdown("---")
        st.subheader("Select an Action")
        if st.button("📱 Take Inventory", disabled=not st.session_state.bevweekly_data, use_container_width=True):
            st.session_state.app_mode = 'scanner'
            st.rerun()

    elif st.session_state.app_mode == 'scanner':
        st.title("📱 Take Inventory")

        if not st.session_state.bevweekly_data:
            st.error("Please go back to the menu and upload a BevWeekly file first.")
            return

        items_list = st.session_state.bevweekly_data['original_order']
        total_items = len(items_list)
        counted_items = len(st.session_state.inventory_counts)
        progress = counted_items / total_items if total_items > 0 else 0
        st.progress(progress, text=f"{counted_items} / {total_items} Items Started ({progress:.0%})")
        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📷 Scan or Search Item")
            scanned_code = barcode_scanner_component()
            if scanned_code and scanned_code != st.session_state.scanned_barcode:
                st.session_state.scanned_barcode = scanned_code
                st.toast(f"Barcode Scanned: {scanned_code}", icon=" barcode ")

            search_query = st.text_input(
                "Search for an item",
                placeholder="e.g., 'Bulleit' or scan a barcode",
                value=st.session_state.scanned_barcode or ""
            )

            if search_query:
                filtered_items = [item for item in items_list if search_query.lower() in item.lower()]
            else:
                uncounted_items = [item for item in items_list if item not in st.session_state.inventory_counts]
                filtered_items = uncounted_items

            selected_item = st.selectbox(
                "Select Item to Count:",
                filtered_items,
                index=0 if filtered_items else None
            )

            if selected_item:
                with st.container():
                    st.markdown(f"#### Counting: **{selected_item}**")
                    
                    # Get current counts for the selected item
                    item_counts = st.session_state.inventory_counts.get(selected_item, [])
                    total_count = sum(item_counts)

                    # Display previous counts and total
                    if item_counts:
                        st.info(f"**Current Total: {total_count}**\n\nCounts entered: `{item_counts}`")

                    # Form for adding a new count
                    with st.form(key=f"form_{selected_item}", clear_on_submit=True):
                        new_count = st.number_input("Add Count:", min_value=0.0, step=0.5, key=f"count_{selected_item}")
                        submitted = st.form_submit_button(f"Add {new_count} to Total", use_container_width=True, type="primary")
                        
                        if submitted and new_count > 0:
                            current_list = st.session_state.inventory_counts.get(selected_item, [])
                            current_list.append(new_count)
                            st.session_state.inventory_counts[selected_item] = current_list
                            st.session_state.scanned_barcode = "" # Clear barcode after use
                            st.rerun()

        with col2:
            st.subheader("📋 Current Inventory Session")
            if not st.session_state.inventory_counts:
                st.info("No items have been counted yet. Use the scanner or search on the left to begin.")
            else:
                # Create DataFrame for display
                display_data = []
                for item, counts in sorted(st.session_state.inventory_counts.items(), key=lambda x: items_list.index(x[0])):
                    display_data.append({
                        "Item": item,
                        "Total": sum(counts),
                        "Counts": str(counts),
                        "Actions": item # Use item name as unique identifier for actions
                    })
                
                df = pd.DataFrame(display_data)

                st.data_editor(
                    df,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Item": st.column_config.TextColumn(disabled=True, width="large"),
                        "Total": st.column_config.NumberColumn(disabled=True),
                        "Counts": st.column_config.TextColumn(disabled=True, width="medium"),
                        "Actions": st.column_config.Column(
                            " ", # No visible header for the button column
                            cell_template=None,
                            # Custom component logic would be needed for a real "delete last" button
                            # For now, this column is a placeholder.
                        )
                    },
                    disabled=["Item", "Total", "Counts", "Actions"]
                )

                st.markdown("---")
                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    if st.button("🗑️ Clear All Counts", use_container_width=True, type="secondary"):
                        st.session_state.inventory_counts.clear()
                        st.rerun()
                with btn_col2:
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


# --- EXPORT FUNCTION (V2) ---
def export_updated_excel():
    """
    Updates the target Excel sheet with summed inventory counts
    using openpyxl to preserve all original formatting.
    """
    if not st.session_state.bevweekly_data or not st.session_state.inventory_counts:
        return None

    try:
        file_stream = BytesIO(st.session_state.uploaded_file_content)
        workbook = openpyxl.load_workbook(file_stream)
        target_sheet_name = st.session_state.bevweekly_data['next_week_sheet']
        sheet = workbook[target_sheet_name]
        item_to_row_map = st.session_state.bevweekly_data['item_to_row_map']
        
        END_INVENTORY_COL = 8
        # Iterate through the counted items and update the cells with the SUM
        for item, counts_list in st.session_state.inventory_counts.items():
            total = sum(counts_list) # Sum the list of counts
            item_clean = item.strip()
            if item_clean in item_to_row_map:
                row_number = item_to_row_map[item_clean]
                sheet.cell(row=row_number, column=END_INVENTORY_COL, value=float(total))

        output_stream = BytesIO()
        workbook.save(output_stream)
        output_stream.seek(0)
        return output_stream.getvalue()

    except Exception as e:
        st.error(f"Error during Excel export: {e}")
        return None

if __name__ == "__main__":
    run_app()