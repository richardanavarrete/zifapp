"""
Data Models - Normalized representation of inventory data.

This module defines the canonical data structures used throughout the agent system.
Items are identified by their display name (e.g., "WHISKEY Buffalo Trace").
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd


@dataclass
class Item:
    """Canonical representation of an inventory item."""
    item_id: str  # e.g., "WHISKEY Buffalo Trace"
    display_name: str
    category: str  # Whiskey, Vodka, etc.
    vendor: str  # Breakthru, Southern, etc.
    location: Optional[str] = None  # From inventory_layout.json

    # Metadata
    unit: str = "bottles"
    case_size: Optional[int] = None

    # Cost data
    unit_cost: Optional[float] = None  # $ per unit (bottle, keg, etc.)
    unit_of_measure: Optional[str] = None  # "Bottle (1 L)", "Keg", etc.

    def __post_init__(self):
        # Ensure item_id is always stripped and consistent
        self.item_id = self.item_id.strip()
        self.display_name = self.display_name.strip()


@dataclass
class WeeklyRecord:
    """A single week's inventory record for an item."""
    item_id: str
    week_date: datetime
    on_hand: float
    usage: float
    week_name: str  # Original sheet name
    source_file: str

    # Cost data
    unit_cost: Optional[float] = None  # $ per unit at this point in time
    usage_cost: Optional[float] = None  # usage × unit_cost
    inventory_value: Optional[float] = None  # on_hand × unit_cost

    def __post_init__(self):
        self.item_id = self.item_id.strip()


@dataclass
class InventoryDataset:
    """Complete inventory dataset with items and records."""
    items: Dict[str, Item]  # item_id -> Item
    records: pd.DataFrame  # Columns: item_id, week_date, on_hand, usage, week_name, source_file

    def get_item(self, item_id: str) -> Optional[Item]:
        """Get item by ID."""
        return self.items.get(item_id.strip())

    def get_item_records(self, item_id: str) -> pd.DataFrame:
        """Get all weekly records for a specific item."""
        return self.records[self.records['item_id'] == item_id.strip()].copy()

    def get_unique_items(self) -> List[str]:
        """Get list of all item IDs."""
        return list(self.items.keys())

    def get_date_range(self) -> tuple:
        """Get (min_date, max_date) from records."""
        if self.records.empty:
            return (None, None)
        return (self.records['week_date'].min(), self.records['week_date'].max())

    def get_total_weeks(self) -> int:
        """Get total number of unique weeks in dataset."""
        return self.records['week_date'].nunique()


def create_dataset_from_excel(uploaded_files) -> InventoryDataset:
    """
    Convert uploaded Excel files into InventoryDataset.

    This replaces the inline logic from load_and_process_data() in zifapp.py.

    Args:
        uploaded_files: Single file or list of UploadedFile objects from Streamlit

    Returns:
        InventoryDataset with items and records populated
    """
    # Handle single file or multiple files
    if not isinstance(uploaded_files, list):
        uploaded_files = [uploaded_files]

    # Process all files
    compiled_records = []
    for uploaded_file in uploaded_files:
        try:
            xls = pd.ExcelFile(uploaded_file)
            sheet_names = xls.sheet_names

            for sheet in sheet_names:
                try:
                    df = xls.parse(sheet, skiprows=4)

                    # Rename columns based on index positions
                    df = df.rename(columns={
                        df.columns[0]: 'Item',
                        df.columns[1]: 'Unit of Measure',
                        df.columns[2]: 'Unit Cost',
                        df.columns[3]: 'BEG INV',
                        df.columns[4]: 'BEG $',
                        df.columns[5]: 'PURCH QTY',
                        df.columns[6]: 'PUR $',
                        df.columns[7]: 'End Inventory',
                        df.columns[9]: 'Usage'
                    })
                    df = df[['Item', 'Unit of Measure', 'Unit Cost', 'BEG INV', 'BEG $', 'PURCH QTY', 'PUR $', 'End Inventory', 'Usage']]
                    df['Week'] = sheet
                    df['Source File'] = uploaded_file.name

                    # Extract date
                    date_value = xls.parse(sheet).iloc[1, 0]
                    df['Date'] = pd.to_datetime(date_value, errors='coerce')
                    compiled_records.append(df)
                except Exception:
                    continue
        except Exception:
            continue

    if not compiled_records:
        # Return empty dataset
        return InventoryDataset(
            items={},
            records=pd.DataFrame(columns=['item_id', 'week_date', 'on_hand', 'usage', 'week_name', 'source_file', 'unit_cost', 'beg_inv_value', 'purchases_value', 'beg_inv_qty', 'purchases_qty', 'end_inv_value', 'usage_cost', 'inventory_value'])
        )

    # Combine all records
    full_df = pd.concat(compiled_records, ignore_index=True)
    full_df = full_df.dropna(subset=['Item', 'Usage'])
    full_df['Item'] = full_df['Item'].astype(str).str.strip()
    full_df = full_df[~full_df['Item'].str.upper().str.startswith('TOTAL')]

    full_df['Usage'] = pd.to_numeric(full_df['Usage'], errors='coerce')
    full_df['End Inventory'] = pd.to_numeric(full_df['End Inventory'], errors='coerce')
    full_df = full_df.dropna(subset=['Usage', 'End Inventory'])

    # Process cost data
    full_df['Unit Cost'] = pd.to_numeric(full_df['Unit Cost'], errors='coerce')
    full_df['Unit of Measure'] = full_df['Unit of Measure'].astype(str).str.strip()

    # Process COGS-related columns
    full_df['BEG $'] = pd.to_numeric(full_df['BEG $'], errors='coerce').fillna(0)
    full_df['PUR $'] = pd.to_numeric(full_df['PUR $'], errors='coerce').fillna(0)
    full_df['BEG INV'] = pd.to_numeric(full_df['BEG INV'], errors='coerce').fillna(0)
    full_df['PURCH QTY'] = pd.to_numeric(full_df['PURCH QTY'], errors='coerce').fillna(0)

    # Remove duplicates (keep last occurrence for overlapping weeks)
    full_df = full_df.drop_duplicates(subset=['Item', 'Date'], keep='last')
    full_df = full_df.sort_values(by=['Item', 'Date'])

    # Build items dictionary (will be enriched by mappings module later)
    # Use most recent cost for each item
    items = {}
    for item_id in full_df['Item'].unique():
        item_data = full_df[full_df['Item'] == item_id].sort_values('Date', ascending=False).iloc[0]
        items[item_id] = Item(
            item_id=item_id,
            display_name=item_id,
            category="Unknown",
            vendor="Unknown",
            unit_cost=item_data['Unit Cost'] if pd.notna(item_data['Unit Cost']) else None,
            unit_of_measure=item_data['Unit of Measure'] if pd.notna(item_data['Unit of Measure']) and item_data['Unit of Measure'] != 'nan' else None
        )

    # Build records dataframe with canonical column names
    records_df = full_df.rename(columns={
        'Item': 'item_id',
        'Date': 'week_date',
        'End Inventory': 'on_hand',
        'Usage': 'usage',
        'Week': 'week_name',
        'Source File': 'source_file',
        'Unit Cost': 'unit_cost',
        'BEG $': 'beg_inv_value',
        'PUR $': 'purchases_value',
        'BEG INV': 'beg_inv_qty',
        'PURCH QTY': 'purchases_qty'
    })[['item_id', 'week_date', 'on_hand', 'usage', 'week_name', 'source_file', 'unit_cost', 'beg_inv_value', 'purchases_value', 'beg_inv_qty', 'purchases_qty']]

    # Calculate cost metrics for each record using TRADITIONAL COGS FORMULA
    # COGS = Beginning Inventory $ + Purchases $ - Ending Inventory $
    records_df['end_inv_value'] = records_df['on_hand'] * records_df['unit_cost']
    records_df['usage_cost'] = records_df['beg_inv_value'] + records_df['purchases_value'] - records_df['end_inv_value']
    records_df['inventory_value'] = records_df['end_inv_value']

    return InventoryDataset(items=items, records=records_df)
