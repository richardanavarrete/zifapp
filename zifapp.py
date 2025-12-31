import streamlit as st
import pandas as pd
from datetime import datetime
import json
import math
import logging
from typing import Dict, List, Tuple, Optional, Any
import re

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Page Configuration (MUST BE THE FIRST STREAMLIT COMMAND) ---
st.set_page_config(page_title="Bev Usage Analyzer", layout="wide")
st.title("🍺 Bev Usage Analyzer")

# --- Load Configuration Files ---
@st.cache_data
def load_configurations() -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """Load vendor and inventory configurations from JSON files."""
    try:
        with open('vendor_map.json', 'r') as f:
            vendor_config = json.load(f)
            vendor_map = {k: [item.strip() for item in v] 
                         for k, v in vendor_config.get('vendor_map', {}).items()}
        
        # Try to load inventory layout if needed
        inventory_layout = {}
        try:
            with open('inventory_layout.json', 'r') as f:
                inventory_layout = json.load(f)
        except FileNotFoundError:
            logger.info("inventory_layout.json not found, continuing without it")
        
        return vendor_map, inventory_layout
    except FileNotFoundError:
        logger.error("vendor_map.json not found")
        st.error("Configuration file 'vendor_map.json' not found. Please ensure it exists.")
        st.stop()
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON configuration: {e}")
        st.error(f"Error parsing configuration file: {e}")
        st.stop()

# --- Category Classification ---
def classify_items_by_category(items: List[str]) -> Dict[str, List[str]]:
    """Classify items into categories based on patterns in their names."""
    
    # Define category patterns with priority order
    category_patterns = [
        # Higher priority patterns (check first)
        ("Well", lambda x: "WELL" in x.upper()),
        ("Draft Beer", lambda x: "BEER DFT" in x.upper()),
        ("Bottled Beer", lambda x: "BEER BTL" in x.upper()),
        
        # Spirit categories
        ("Whiskey", lambda x: "WHISKEY" in x.upper()),
        ("Vodka", lambda x: "VODKA" in x.upper()),
        ("Gin", lambda x: "GIN" in x.upper()),
        ("Tequila", lambda x: "TEQUILA" in x.upper()),
        ("Rum", lambda x: "RUM" in x.upper()),
        ("Scotch", lambda x: "SCOTCH" in x.upper()),
        ("Brandy", lambda x: "BRANDY" in x.upper()),
        
        # Liqueurs and cordials
        ("Cordials", lambda x: "SCHNAPPS" in x.upper()),
        ("Liqueur", lambda x: "LIQ" in x.upper() and "SCHNAPPS" not in x.upper()),
        
        # Wine and other
        ("Wine", lambda x: "WINE" in x.upper()),
        ("Juice", lambda x: "JUICE" in x.upper()),
        ("Bar Consumables", lambda x: "BAR CONS" in x.upper()),
    ]
    
    category_map = {cat: [] for cat, _ in category_patterns}
    category_map["Other"] = []  # For uncategorized items
    
    for item in items:
        categorized = False
        for category, pattern_func in category_patterns:
            if pattern_func(item):
                category_map[category].append(item)
                categorized = True
                break
        
        if not categorized:
            category_map["Other"].append(item)
    
    # Remove empty categories
    return {k: v for k, v in category_map.items() if v}

# --- Safe Data Operations ---
def safe_get_value(series: pd.Series, index: int, default: Any = None) -> Any:
    """Safely get a value from a pandas Series by index."""
    try:
        if not series.empty and len(series) > abs(index):
            return series.iloc[index]
    except (IndexError, KeyError):
        pass
    return default

def safe_divide(numerator: float, denominator: float, round_digits: int = 2) -> Optional[float]:
    """Safely divide two numbers, returning None if division is not possible."""
    if pd.notna(denominator) and denominator != 0:
        return round(numerator / denominator, round_digits)
    return None

# --- Data Processing ---
@st.cache_data
def load_and_process_data(uploaded_file) -> Tuple[pd.DataFrame, Dict[str, List[str]], Dict[str, List[str]]]:
    """
    Reads the uploaded Excel file, processes all data, and calculates summary metrics.
    This function is cached to prevent re-running on every widget interaction.
    """
    try:
        xls = pd.ExcelFile(uploaded_file)
        sheet_names = xls.sheet_names
        
        if not sheet_names:
            raise ValueError("No sheets found in the Excel file")
        
        # Get original item order with error handling
        try:
            original_order_df = xls.parse(sheet_names[0], skiprows=4)
            if original_order_df.empty or len(original_order_df.columns) == 0:
                raise ValueError("First sheet appears to be empty")
            
            original_order = original_order_df.iloc[:, 0].dropna().astype(str).str.strip().tolist()
        except Exception as e:
            logger.warning(f"Could not extract original order: {e}")
            original_order = []
        
        # Process all sheets
        compiled_data = []
        for sheet_name in sheet_names:
            try:
                df = process_single_sheet(xls, sheet_name)
                if df is not None and not df.empty:
                    compiled_data.append(df)
            except Exception as e:
                logger.warning(f"Error processing sheet '{sheet_name}': {e}")
                continue
        
        if not compiled_data:
            raise ValueError("No valid data could be extracted from any sheet")
        
        # Combine all data
        full_df = pd.concat(compiled_data, ignore_index=True)
        full_df = clean_dataframe(full_df)
        
        # Calculate summary metrics
        summary_df = calculate_summary_metrics(full_df, original_order)
        
        # Load configurations
        vendor_map, _ = load_configurations()
        
        # Classify items by category
        all_items = summary_df['Item'].unique().tolist()
        category_map = classify_items_by_category(all_items)
        
        return summary_df, vendor_map, category_map
    
    except Exception as e:
        logger.error(f"Error processing data: {e}")
        raise

def process_single_sheet(xls: pd.ExcelFile, sheet_name: str) -> Optional[pd.DataFrame]:
    """Process a single sheet from the Excel file."""
    try:
        # Read the sheet
        df = xls.parse(sheet_name, skiprows=4)
        
        if df.empty:
            return None
        
        # Identify columns by content rather than position
        df = identify_and_rename_columns(df)
        
        if 'Item' not in df.columns or 'Usage' not in df.columns:
            logger.warning(f"Sheet '{sheet_name}' missing required columns")
            return None
        
        # Select required columns
        required_cols = ['Item', 'Usage']
        optional_cols = ['End Inventory']
        
        cols_to_keep = required_cols + [col for col in optional_cols if col in df.columns]
        df = df[cols_to_keep]
        
        # Add metadata
        df['Week'] = sheet_name
        
        # Try to extract date
        try:
            date_value = xls.parse(sheet_name).iloc[1, 0]
            df['Date'] = pd.to_datetime(date_value, errors='coerce')
        except:
            df['Date'] = pd.NaT
        
        return df
    
    except Exception as e:
        logger.error(f"Error processing sheet {sheet_name}: {e}")
        return None

def identify_and_rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Identify and rename columns based on their content patterns."""
    new_columns = {}
    
    for idx, col in enumerate(df.columns):
        # Check first few rows for patterns
        sample = df.iloc[:5, idx].dropna().astype(str)
        
        if sample.empty:
            continue
        
        # Check for item names (usually contains product types)
        if any(any(keyword in str(val).upper() for keyword in ['VODKA', 'WHISKEY', 'BEER', 'WINE', 'RUM', 'GIN']) 
               for val in sample):
            if 'Item' not in new_columns.values():
                new_columns[col] = 'Item'
        
        # Check for numeric columns by position and content
        elif idx == 9 or (sample.apply(lambda x: x.replace('.', '').replace('-', '').isdigit()).any() and idx > 5):
            if 'Usage' not in new_columns.values() and idx >= 7:
                new_columns[col] = 'Usage'
        
        elif idx == 7 or (idx > 5 and idx < 9):
            if 'End Inventory' not in new_columns.values():
                new_columns[col] = 'End Inventory'
    
    # Apply renaming
    df = df.rename(columns=new_columns)
    return df

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and standardize the dataframe."""
    # Remove null items
    df = df.dropna(subset=['Item', 'Usage'])
    
    # Standardize item names
    df['Item'] = df['Item'].astype(str).str.strip()
    
    # Remove total rows
    df = df[~df['Item'].str.upper().str.startswith('TOTAL')]
    
    # Convert numeric columns
    numeric_cols = ['Usage', 'End Inventory']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Remove rows with invalid numeric data
    df = df.dropna(subset=['Usage'])
    
    # Fill missing End Inventory with 0
    if 'End Inventory' in df.columns:
        df['End Inventory'] = df['End Inventory'].fillna(0)
    else:
        df['End Inventory'] = 0
    
    # Sort by item and date
    if 'Date' in df.columns:
        df = df.sort_values(by=['Item', 'Date'])
    else:
        df = df.sort_values(by=['Item'])
    
    return df

def calculate_summary_metrics(full_df: pd.DataFrame, original_order: List[str]) -> pd.DataFrame:
    """Calculate summary metrics for each item."""
    
    def compute_metrics(group: pd.DataFrame) -> pd.Series:
        """Compute metrics for a single item group."""
        usage = group['Usage']
        inventory = group['End Inventory']
        dates = group.get('Date', pd.Series([pd.NaT] * len(group)))
        
        # Safe value extraction valid_inventory = inventory[(inventory.notna()) & (inventory > 0)]
        if not valid_inventory.empty:
            last_inventory = valid_inventory.iloc[-1]
            # Get the index of this inventory value to align usage data
            last_valid_index = valid_inventory.index[-1]
            # Get usage up to the last valid inventory point
            usage_to_date = usage.loc[:last_valid_index]
        else:
            # Fallback if no valid inventory found
            last_inventory = 0
            usage_to_date = usage
        
        # Calculate averages
        last_10 = usage.tail(10)
        last_4 = usage.tail(4)
        
        # Year-to-date average
        ytd_avg = None
        if 'Date' in group.columns and pd.api.types.is_datetime64_any_dtype(dates):
            current_year_data = group[dates.dt.year == datetime.now().year]['Usage']
            if not current_year_data.empty:
                ytd_avg = current_year_data.mean()
        
        # Highest and lowest averages
        avg_of_highest_4 = usage.nlargest(4).mean() if len(usage) >= 4 else usage.mean()
        non_zero_usage = usage[usage > 0]
        avg_of_lowest_4_non_zero = (non_zero_usage.nsmallest(4).mean() 
                                    if len(non_zero_usage) >= 4 
                                    else non_zero_usage.mean() if not non_zero_usage.empty 
                                    else None)
        
        # Calculate weeks remaining
        avg_10 = last_10.mean() if not last_10.empty else 0
        avg_4 = last_4.mean() if not last_4.empty else 0
        max_usage = usage.max() if not usage.empty else 0
        
        return pd.Series({
            'On Hand': round(last_inventory, 2),
            'Last Week Usage': round(last_week_usage, 2),
            'Year-to-Date Average': round(ytd_avg, 2) if ytd_avg is not None else None,
            '10-Week Average': round(avg_10, 2),
            '4-Week Average': round(avg_4, 2),
            'All-Time High': round(max_usage, 2),
            'Lowest 4 Average (non-zero)': round(avg_of_lowest_4_non_zero, 2) if avg_of_lowest_4_non_zero else None,
            'Highest 4 Average': round(avg_of_highest_4, 2) if avg_of_highest_4 else None,
            'Weeks Remaining (YTD)': safe_divide(last_inventory, ytd_avg) if ytd_avg else None,
            'Weeks Remaining (10 Wk)': safe_divide(last_inventory, avg_10),
            'Weeks Remaining (4 Wk)': safe_divide(last_inventory, avg_4),
            'Weeks Remaining (ATH)': safe_divide(last_inventory, max_usage),
            'Weeks Remaining (Lowest 4)': safe_divide(last_inventory, avg_of_lowest_4_non_zero) if avg_of_lowest_4_non_zero else None,
            'Weeks Remaining (Highest 4)': safe_divide(last_inventory, avg_of_highest_4) if avg_of_highest_4 else None
        })
    
    # Group by item and calculate metrics
    summary_df = full_df.groupby('Item').apply(compute_metrics).reset_index()
    
    # Apply original ordering if available
    if original_order:
        summary_df['ItemOrder'] = summary_df['Item'].apply(
            lambda x: original_order.index(x) if x in original_order else float('inf')
        )
        summary_df = summary_df.sort_values(by='ItemOrder').drop(columns='ItemOrder')
    
    return summary_df

# --- UI Helper Functions ---
def highlight_weeks_remaining(val, threshold: float = 2.0) -> str:
    """Highlight cells with low weeks remaining."""
    if pd.notna(val) and isinstance(val, (int, float)) and val < threshold:
        return 'background-color: #ff4b4b'
    return ''

def format_dataframe_for_display(df: pd.DataFrame, threshold: float = 2.0):
    """Format dataframe for display with styling."""
    format_dict = {
        col: '{:,.2f}' for col in df.select_dtypes(include=['float64', 'float32']).columns
    }
    
    weeks_columns = [col for col in df.columns if 'Weeks Remaining' in col]
    
    styled_df = df.style.format(format_dict, na_rep="-")
    
    if weeks_columns:
        styled_df = styled_df.applymap(
            lambda val: highlight_weeks_remaining(val, threshold),
            subset=weeks_columns
        )
    
    return styled_df

# --- Worksheet Functions ---
def render_worksheet_table(
    items_to_display: List[str],
    summary_df: pd.DataFrame,
    usage_option: str,
    key_prefix: str,
    category_map: Dict[str, List[str]]
):
    """Render the worksheet table for ordering."""
    worksheet_state_key = f"worksheet_df_{key_prefix}"
    usage_state_key = f"usage_option_{key_prefix}"
    
    # Master slider and Apply button
    st.markdown("---")
    col1, col2 = st.columns([3, 1])
    with col1:
        bulk_week_target = st.slider(
            "Set a target for all items in this tab:",
            min_value=0.0, max_value=12.0, value=4.0, step=0.1, 
            key=f"slider_{key_prefix}"
        )
    with col2:
        st.write("")
        if st.button("Apply to All", use_container_width=True, key=f"button_{key_prefix}"):
            apply_bulk_target(worksheet_state_key, bulk_week_target)
    
    st.markdown("---")
    
    # Initialize or update worksheet
    if (worksheet_state_key not in st.session_state or 
        st.session_state.get(usage_state_key) != usage_option):
        
        initialize_worksheet(
            worksheet_state_key, 
            usage_state_key,
            items_to_display, 
            summary_df, 
            usage_option
        )
    
    # Display data editor
    edited_df = st.data_editor(
        st.session_state[worksheet_state_key],
        hide_index=True,
        use_container_width=True,
        key=f"editor_{key_prefix}",
        column_config={
            "Item": st.column_config.TextColumn(disabled=True),
            "On Hand": st.column_config.NumberColumn(format="%.2f", disabled=True),
            "Current Wks Left": st.column_config.NumberColumn(
                format="%.1f", 
                help="Current inventory in weeks of supply.", 
                disabled=True
            ),
            "Selected Avg": st.column_config.NumberColumn(
                f"Avg Usage ({usage_option})", 
                format="%.2f", 
                disabled=True
            ),
            "Order Qty (Bottles)": st.column_config.NumberColumn(
                min_value=0, step=1, format="%d"
            ),
            "Target Weeks of Supply": st.column_config.NumberColumn(
                help="Enter a target total weeks of supply", 
                min_value=0.0, step=0.1, format="%.1f"
            )
        }
    )
    
    # Handle edits
    handle_worksheet_edits(edited_df, worksheet_state_key)
    
    # Generate order summary
    st.markdown("---")
    if st.button("Generate Final Order Summary", key=f"finalize_{key_prefix}"):
        generate_order_summary(worksheet_state_key, key_prefix)
    
    # Keg counter for specific views
    display_keg_counter(key_prefix, worksheet_state_key, category_map)

def initialize_worksheet(
    worksheet_state_key: str,
    usage_state_key: str,
    items: List[str],
    summary_df: pd.DataFrame,
    usage_option: str
):
    """Initialize the worksheet dataframe."""
    filtered_df = summary_df[summary_df['Item'].isin(items)]
    
    worksheet_data = {
        'Item': filtered_df['Item'].values,
        'On Hand': filtered_df['On Hand'].values,
        'Selected Avg': filtered_df[usage_option].fillna(0).values,
        'Order Qty (Bottles)': [0] * len(filtered_df),
        'Target Weeks of Supply': [0.0] * len(filtered_df)
    }
    
    worksheet_df = pd.DataFrame(worksheet_data)
    worksheet_df['Current Wks Left'] = worksheet_df.apply(
        lambda row: safe_divide(row['On Hand'], row['Selected Avg'], 1) or 0.0,
        axis=1
    )
    
    # Reorder columns
    worksheet_df = worksheet_df[[
        'Item', 'On Hand', 'Current Wks Left', 
        'Selected Avg', 'Order Qty (Bottles)', 'Target Weeks of Supply'
    ]]
    
    st.session_state[worksheet_state_key] = worksheet_df
    st.session_state[usage_state_key] = usage_option
    st.session_state.pop('last_edited_column', None)
    st.rerun()

def apply_bulk_target(worksheet_state_key: str, target_weeks: float):
    """Apply bulk target weeks to all items."""
    if worksheet_state_key in st.session_state:
        df = st.session_state[worksheet_state_key].copy()
        df['Target Weeks of Supply'] = target_weeks
        df['Order Qty (Bottles)'] = df.apply(
            lambda r: max(0, int(math.ceil((r['Target Weeks of Supply'] * r['Selected Avg']) - r['On Hand'])))
            if r['Selected Avg'] > 0 else 0,
            axis=1
        )
        st.session_state[worksheet_state_key] = df
        st.rerun()

def handle_worksheet_edits(edited_df: pd.DataFrame, worksheet_state_key: str):
    """Handle edits to the worksheet."""
    if worksheet_state_key not in st.session_state:
        return
    
    current_df = st.session_state[worksheet_state_key]
    
    # Check if dataframes are different (using a more robust comparison)
    if not dataframes_equal(edited_df, current_df):
        # Detect which column was edited
        bottles_changed = not series_equal(
            edited_df['Order Qty (Bottles)'], 
            current_df['Order Qty (Bottles)']
        )
        weeks_changed = not series_equal(
            edited_df['Target Weeks of Supply'], 
            current_df['Target Weeks of Supply']
        )
        
        if bottles_changed:
            st.session_state.last_edited_column = 'Bottles'
        elif weeks_changed:
            st.session_state.last_edited_column = 'Weeks'
        
        new_df = edited_df.copy()
        
        # Update based on which column was edited
        if st.session_state.get('last_edited_column') == 'Bottles':
            new_df['Target Weeks of Supply'] = new_df.apply(
                lambda r: safe_divide(r['On Hand'] + r['Order Qty (Bottles)'], r['Selected Avg'], 1) or 0,
                axis=1
            )
        elif st.session_state.get('last_edited_column') == 'Weeks':
            new_df['Order Qty (Bottles)'] = new_df.apply(
                lambda r: max(0, int(math.ceil((r['Target Weeks of Supply'] * r['Selected Avg']) - r['On Hand'])))
                if r['Selected Avg'] > 0 else 0,
                axis=1
            )
        
        st.session_state[worksheet_state_key] = new_df
        st.rerun()

def dataframes_equal(df1: pd.DataFrame, df2: pd.DataFrame, tolerance: float = 1e-5) -> bool:
    """Check if two dataframes are equal with tolerance for floating point comparisons."""
    if df1.shape != df2.shape:
        return False
    
    for col in df1.columns:
        if not series_equal(df1[col], df2[col], tolerance):
            return False
    
    return True

def series_equal(s1: pd.Series, s2: pd.Series, tolerance: float = 1e-5) -> bool:
    """Check if two series are equal with tolerance for floating point comparisons."""
    if len(s1) != len(s2):
        return False
    
    if s1.dtype == 'float64' or s2.dtype == 'float64':
        return ((s1 - s2).abs() < tolerance).all()
    else:
        return s1.equals(s2)

def generate_order_summary(worksheet_state_key: str, key_prefix: str):
    """Generate the final order summary."""
    order_df = st.session_state[worksheet_state_key]
    items_to_order = order_df[order_df['Order Qty (Bottles)'] > 0]
    
    if items_to_order.empty:
        st.warning("No items have been marked for order.")
        return
    
    results = []
    for _, row in items_to_order.iterrows():
        on_hand = row['On Hand']
        bottles_to_order = row['Order Qty (Bottles)']
        new_total = on_hand + bottles_to_order
        new_weeks = safe_divide(new_total, row['Selected Avg'], 1) or 0.0
        
        results.append({
            'Item': row['Item'],
            'Current On Hand': on_hand,
            'Bottles to Order': int(bottles_to_order),
            'New Total On Hand': round(new_total, 2),
            'New Weeks of Supply': new_weeks
        })
    
    result_df = pd.DataFrame(results)
    
    st.subheader("Final Order Summary")
    st.dataframe(result_df, use_container_width=True, hide_index=True)
    
    csv_order = result_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        "Download Final Order CSV",
        data=csv_order,
        file_name=f"final_order_summary_{key_prefix}.csv"
    )

def display_keg_counter(
    key_prefix: str, 
    worksheet_state_key: str, 
    category_map: Dict[str, List[str]]
):
    """Display keg counter for relevant views."""
    views_with_keg_counter = ["Crescent", "Hensley", "Draft Beer"]
    
    if key_prefix in views_with_keg_counter:
        current_order_df = st.session_state.get(worksheet_state_key, pd.DataFrame())
        if not current_order_df.empty:
            draft_beer_items = category_map.get("Draft Beer", [])
            kegs_on_order = current_order_df[current_order_df['Item'].isin(draft_beer_items)]
            total_kegs_ordered = kegs_on_order['Order Qty (Bottles)'].sum()
            st.metric(
                label="Total Kegs to Order in this Tab",
                value=f"{total_kegs_ordered:,.0f}"
            )

# --- Main Application ---
def main():
    """Main application logic."""
    uploaded_file = st.file_uploader("Upload your BEVWEEKLY Excel File", type="xlsx")
    
    if not uploaded_file:
        st.info("Please upload a BEVWEEKLY Excel file to begin.")
        return
    
    try:
        summary_df, vendor_map, category_map = load_and_process_data(uploaded_file)
    except Exception as e:
        st.error(f"An error occurred during data processing: {e}")
        logger.error(f"Data processing error: {e}", exc_info=True)
        return
    
    # Create tabs
    tab_summary, tab_ordering = st.tabs(["📊 Summary", "🧪 Ordering Worksheet"])
    
    # Summary Tab
    with tab_summary:
        render_summary_tab(summary_df, vendor_map, category_map)
    
    # Ordering Worksheet Tab
    with tab_ordering:
        render_ordering_tab(summary_df, vendor_map, category_map)

def render_summary_tab(
    summary_df: pd.DataFrame, 
    vendor_map: Dict[str, List[str]], 
    category_map: Dict[str, List[str]]
):
    """Render the summary tab."""
    st.subheader("Usage Summary")
    
    filter_type = st.radio(
        "Filter By:", 
        ["Vendor", "Category"], 
        horizontal=True, 
        key="summary_filter_type"
    )
    
    display_df = summary_df.copy()
    download_filename = "beverage_summary_full.csv"
    
    if filter_type == "Vendor":
        vendor_options = ["All Vendors"] + list(vendor_map.keys())
        selected_vendor = st.selectbox(
            "Select Vendor", 
            options=vendor_options, 
            key="summary_vendor_select"
        )
        
        if selected_vendor != "All Vendors":
            display_df = summary_df[summary_df['Item'].isin(vendor_map.get(selected_vendor, []))]
            download_filename = f"beverage_summary_{selected_vendor}.csv"
    
    elif filter_type == "Category":
        category_options = ["All Categories"] + list(category_map.keys())
        selected_category = st.selectbox(
            "Select Category", 
            options=category_options, 
            key="summary_category_select"
        )
        
        if selected_category != "All Categories":
            display_df = summary_df[summary_df['Item'].isin(category_map.get(selected_category, []))]
            download_filename = f"beverage_summary_{selected_category}.csv"
    
    # Threshold slider
    threshold = st.slider(
        "Highlight if weeks remaining is below:",
        min_value=0.2,
        max_value=10.0,
        value=2.0,
        step=0.1
    )
    
    # Display formatted dataframe
    styled_df = format_dataframe_for_display(display_df, threshold)
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    # Download button
    csv = display_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        "Download Summary CSV",
        data=csv,
        file_name=download_filename
    )

def render_ordering_tab(
    summary_df: pd.DataFrame,
    vendor_map: Dict[str, List[str]],
    category_map: Dict[str, List[str]]
):
    """Render the ordering worksheet tab."""
    st.subheader("🧪 Ordering Worksheet: Inventory Planning")
    
    mode = st.selectbox("Select View Mode:", ["By Category"])
    
    usage_option = st.selectbox(
        "Select usage average for calculation:",
        options=[
            '10-Week Average',
            '4-Week Average',
            'Year-to-Date Average',
            'Lowest 4 Average (non-zero)',
            'Highest 4 Average'
        ],
        index=1,
        key="usage_radio"
    )
    
    if mode == "By Vendor":
        vendor_keys = list(vendor_map.keys())
        vendor_tabs = st.tabs(vendor_keys)
        
        for i, tab in enumerate(vendor_tabs):
            with tab:
                vendor_name = vendor_keys[i]
                render_worksheet_table(
                    vendor_map.get(vendor_name, []),
                    summary_df,
                    usage_option,
                    vendor_name,
                    category_map
                )
    else:
        category_keys = list(category_map.keys())
        category_tabs = st.tabs(category_keys)
        
        for i, tab in enumerate(category_tabs):
            with tab:
                category_name = category_keys[i]
                render_worksheet_table(
                    category_map.get(category_name, []),
                    summary_df,
                    usage_option,
                    category_name,
                    category_map
                )

# --- Run the application ---
if __name__ == "__main__":
    main()


