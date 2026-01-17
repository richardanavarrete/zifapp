"""
Data Models - Normalized representation of inventory data.

This module defines the canonical data structures used throughout the agent system.
Items are identified by their display name (e.g., "WHISKEY Buffalo Trace").
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
import numpy as np


@dataclass
class WeeklyCOGSSummary:
    """Summary COGS data extracted from the 'Weekly COGS' section of spreadsheet."""
    week_date: datetime
    week_name: str
    source_file: str
    is_complete: bool  # True if all COGS values are valid (not #DIV/0! or NaN)

    # COGS by category (directly from spreadsheet's "Weekly COGS" section)
    liquor_cogs: Optional[float] = None
    wine_cogs: Optional[float] = None
    draft_beer_cogs: Optional[float] = None
    bottle_beer_cogs: Optional[float] = None
    juice_cogs: Optional[float] = None
    total_cogs: Optional[float] = None

    # Sales by category
    liquor_sales: Optional[float] = None
    wine_sales: Optional[float] = None
    draft_beer_sales: Optional[float] = None
    bottle_beer_sales: Optional[float] = None
    juice_sales: Optional[float] = None
    total_sales: Optional[float] = None


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
    weekly_cogs_summaries: List[WeeklyCOGSSummary] = field(default_factory=list)  # Weekly COGS from spreadsheet

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

    def get_latest_complete_cogs_summary(self) -> Optional[WeeklyCOGSSummary]:
        """Get the most recent complete (non-zero ending inventory) weekly COGS summary."""
        complete_summaries = [s for s in self.weekly_cogs_summaries if s.is_complete]
        if not complete_summaries:
            return None
        # Sort by date and return most recent
        complete_summaries.sort(key=lambda x: x.week_date, reverse=True)
        return complete_summaries[0]

    def get_complete_cogs_summaries(self, n: int = 4) -> List[WeeklyCOGSSummary]:
        """Get the N most recent complete weekly COGS summaries."""
        complete_summaries = [s for s in self.weekly_cogs_summaries if s.is_complete]
        complete_summaries.sort(key=lambda x: x.week_date, reverse=True)
        return complete_summaries[:n]

    def get_all_cogs_summaries(self) -> List[WeeklyCOGSSummary]:
        """Get all weekly COGS summaries sorted by date (most recent first)."""
        summaries = self.weekly_cogs_summaries.copy()
        summaries.sort(key=lambda x: x.week_date, reverse=True)
        return summaries

    def get_cogs_summary_by_name(self, week_name: str) -> Optional[WeeklyCOGSSummary]:
        """Get a specific weekly COGS summary by week name (e.g., 'Q1 WK3')."""
        for summary in self.weekly_cogs_summaries:
            if summary.week_name == week_name:
                return summary
        return None


@dataclass
class VoiceCountRecord:
    """Individual item count from voice input."""
    record_id: str  # UUID
    session_id: str  # Links to VoiceCountSession
    timestamp: datetime
    raw_transcript: str  # Original speech-to-text output
    cleaned_transcript: Optional[str] = None  # User-edited version
    matched_item_id: Optional[str] = None  # Matched Item.item_id
    count_value: Optional[float] = None  # Counted quantity
    confidence_score: float = 0.0  # 0.0-1.0 fuzzy match confidence
    match_method: str = "manual"  # "exact", "fuzzy", "manual"
    is_verified: bool = False  # User confirmed the match
    location: Optional[str] = None  # Physical location during count
    notes: Optional[str] = None

    def __post_init__(self):
        # Use cleaned_transcript as raw_transcript if not set
        if self.cleaned_transcript is None:
            self.cleaned_transcript = self.raw_transcript


@dataclass
class VoiceCountSession:
    """A complete voice counting session."""
    session_id: str  # UUID
    created_at: datetime
    updated_at: datetime
    session_name: str  # "Friday Evening Count", etc.
    status: str = "in_progress"  # "in_progress", "completed", "exported"
    total_items_counted: int = 0
    records: List[VoiceCountRecord] = field(default_factory=list)
    inventory_order: List[str] = field(default_factory=list)  # item_ids in sheet order for export
    template_file_name: Optional[str] = None  # Name of uploaded Excel template used for ordering

    def add_record(self, record: VoiceCountRecord):
        """Add a voice count record to this session."""
        self.records.append(record)
        self.total_items_counted = len(self.records)
        self.updated_at = datetime.now()

    def get_verified_records(self) -> List[VoiceCountRecord]:
        """Get only verified records."""
        return [r for r in self.records if r.is_verified]

    def get_unmatched_records(self) -> List[VoiceCountRecord]:
        """Get records that don't have a matched item."""
        return [r for r in self.records if r.matched_item_id is None]

    def get_low_confidence_records(self, threshold: float = 0.7) -> List[VoiceCountRecord]:
        """Get records with confidence below threshold."""
        return [r for r in self.records if r.matched_item_id and r.confidence_score < threshold]


def _parse_weekly_cogs_section(xls, sheet: str, week_date, source_file: str) -> Optional[WeeklyCOGSSummary]:
    """
    Parse the 'Weekly COGS' summary section from a sheet.

    The BEVWEEKLY spreadsheet has a 'Weekly COGS' section that contains
    pre-calculated COGS values by category (LIQUOR, WINE, DRAFT BEER, BOTTLE BEER, JUICE).

    Args:
        xls: pandas ExcelFile object
        sheet: Sheet name
        week_date: Date for this week
        source_file: Source file name

    Returns:
        WeeklyCOGSSummary if found, None otherwise
    """
    try:
        # Read the full sheet without skipping rows to find the Weekly COGS section
        full_sheet = xls.parse(sheet, header=None)

        # Find the row containing "Weekly COGS" text
        weekly_cogs_row = None
        for idx, row in full_sheet.iterrows():
            row_str = ' '.join(str(v) for v in row.values if pd.notna(v))
            if 'weekly cogs' in row_str.lower():
                weekly_cogs_row = idx
                break

        if weekly_cogs_row is None:
            return None

        # The category data starts a few rows after "Weekly COGS" header
        # Look for LIQUOR, WINE, DRAFT BEER, BOTTLE BEER, JUICE rows
        categories = {}
        search_start = weekly_cogs_row + 1
        search_end = min(weekly_cogs_row + 15, len(full_sheet))  # Search up to 15 rows below

        for idx in range(search_start, search_end):
            row = full_sheet.iloc[idx]
            first_cell = str(row.iloc[0]).strip().upper() if pd.notna(row.iloc[0]) else ''

            if first_cell in ['LIQUOR', 'WINE', 'DRAFT BEER', 'BOTTLE BEER', 'JUICE', 'TOTAL']:
                # Column layout from screenshots:
                # 0: PRODUCT, 1: SALES, 2: BEG INV, 3: PURCH, 4: END INV, 5: COGS, ...
                sales_val = pd.to_numeric(row.iloc[1], errors='coerce') if len(row) > 1 else None
                cogs_val = pd.to_numeric(row.iloc[5], errors='coerce') if len(row) > 5 else None

                categories[first_cell] = {
                    'sales': sales_val,
                    'cogs': cogs_val
                }

        if not categories:
            return None

        # Check if the week is complete (all required categories have valid COGS values)
        # A week is incomplete if COGS values are NaN (which happens when ending inventory isn't filled in)
        required_categories = ['LIQUOR', 'WINE', 'DRAFT BEER', 'BOTTLE BEER', 'JUICE']
        is_complete = all(
            categories.get(cat, {}).get('cogs') is not None and
            pd.notna(categories.get(cat, {}).get('cogs'))
            for cat in required_categories
        )

        # Also check that total COGS is valid
        total_cogs = categories.get('TOTAL', {}).get('cogs')
        if total_cogs is None or pd.isna(total_cogs) or total_cogs == 0:
            is_complete = False

        return WeeklyCOGSSummary(
            week_date=week_date,
            week_name=sheet,
            source_file=source_file,
            is_complete=is_complete,
            liquor_cogs=categories.get('LIQUOR', {}).get('cogs'),
            wine_cogs=categories.get('WINE', {}).get('cogs'),
            draft_beer_cogs=categories.get('DRAFT BEER', {}).get('cogs'),
            bottle_beer_cogs=categories.get('BOTTLE BEER', {}).get('cogs'),
            juice_cogs=categories.get('JUICE', {}).get('cogs'),
            total_cogs=total_cogs,
            liquor_sales=categories.get('LIQUOR', {}).get('sales'),
            wine_sales=categories.get('WINE', {}).get('sales'),
            draft_beer_sales=categories.get('DRAFT BEER', {}).get('sales'),
            bottle_beer_sales=categories.get('BOTTLE BEER', {}).get('sales'),
            juice_sales=categories.get('JUICE', {}).get('sales'),
            total_sales=categories.get('TOTAL', {}).get('sales'),
        )
    except Exception:
        return None


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
    weekly_cogs_summaries = []

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
                    week_date = pd.to_datetime(date_value, errors='coerce')
                    df['Date'] = week_date
                    compiled_records.append(df)

                    # Parse the Weekly COGS summary section
                    cogs_summary = _parse_weekly_cogs_section(xls, sheet, week_date, uploaded_file.name)
                    if cogs_summary:
                        weekly_cogs_summaries.append(cogs_summary)
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

    # Sort weekly COGS summaries by date and remove duplicates (keep last)
    weekly_cogs_summaries.sort(key=lambda x: x.week_date)
    seen_dates = set()
    unique_summaries = []
    for summary in reversed(weekly_cogs_summaries):
        date_key = summary.week_date.date() if hasattr(summary.week_date, 'date') else summary.week_date
        if date_key not in seen_dates:
            seen_dates.add(date_key)
            unique_summaries.append(summary)
    unique_summaries.reverse()  # Restore chronological order

    return InventoryDataset(items=items, records=records_df, weekly_cogs_summaries=unique_summaries)
