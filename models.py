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
                        df.columns[9]: 'Usage',
                        df.columns[7]: 'End Inventory'
                    })
                    df = df[['Item', 'Usage', 'End Inventory']]
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
            records=pd.DataFrame(columns=['item_id', 'week_date', 'on_hand', 'usage', 'week_name', 'source_file'])
        )

    # Combine all records
    full_df = pd.concat(compiled_records, ignore_index=True)
    full_df = full_df.dropna(subset=['Item', 'Usage'])
    full_df['Item'] = full_df['Item'].astype(str).str.strip()
    full_df = full_df[~full_df['Item'].str.upper().str.startswith('TOTAL')]

    full_df['Usage'] = pd.to_numeric(full_df['Usage'], errors='coerce')
    full_df['End Inventory'] = pd.to_numeric(full_df['End Inventory'], errors='coerce')
    full_df = full_df.dropna(subset=['Usage', 'End Inventory'])

    # Remove duplicates (keep last occurrence for overlapping weeks)
    full_df = full_df.drop_duplicates(subset=['Item', 'Date'], keep='last')
    full_df = full_df.sort_values(by=['Item', 'Date'])

    # Build items dictionary (will be enriched by mappings module later)
    unique_items = full_df['Item'].unique()
    items = {
        item_id: Item(
            item_id=item_id,
            display_name=item_id,
            category="Unknown",
            vendor="Unknown"
        )
        for item_id in unique_items
    }

    # Build records dataframe with canonical column names
    records_df = full_df.rename(columns={
        'Item': 'item_id',
        'Date': 'week_date',
        'End Inventory': 'on_hand',
        'Usage': 'usage',
        'Week': 'week_name',
        'Source File': 'source_file'
    })[['item_id', 'week_date', 'on_hand', 'usage', 'week_name', 'source_file']]

    return InventoryDataset(items=items, records=records_df)
