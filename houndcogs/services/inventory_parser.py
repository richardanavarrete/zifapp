"""
Inventory File Parser

Parses Excel and CSV inventory files into InventoryDataset models.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import re

import pandas as pd

from houndcogs.models.inventory import (
    Item,
    WeeklyRecord,
    InventoryDataset,
    UploadResult,
)
from houndcogs.models.common import Category, Vendor

logger = logging.getLogger(__name__)


def parse_inventory_file(
    file_path: str,
    dataset_id: str,
    dataset_name: str,
) -> Tuple[InventoryDataset, List[str]]:
    """
    Parse an inventory Excel file into an InventoryDataset.

    Args:
        file_path: Path to the Excel file
        dataset_id: Unique ID for the dataset
        dataset_name: Human-readable name

    Returns:
        Tuple of (InventoryDataset, list of warning messages)

    Raises:
        ValueError: If file format is invalid
    """
    warnings = []
    path = Path(file_path)

    if not path.exists():
        raise ValueError(f"File not found: {file_path}")

    if path.suffix.lower() not in ('.xlsx', '.xls'):
        raise ValueError(f"Unsupported file format: {path.suffix}")

    logger.info(f"Parsing inventory file: {file_path}")

    # Load Excel file
    try:
        xls = pd.ExcelFile(file_path)
    except Exception as e:
        raise ValueError(f"Failed to read Excel file: {e}")

    # Parse each sheet
    all_records = []
    items_dict: Dict[str, Item] = {}

    for sheet_name in xls.sheet_names:
        try:
            records, items, sheet_warnings = _parse_sheet(xls, sheet_name)
            all_records.extend(records)
            items_dict.update(items)
            warnings.extend(sheet_warnings)
        except Exception as e:
            warnings.append(f"Failed to parse sheet '{sheet_name}': {e}")

    if not all_records:
        raise ValueError("No valid inventory records found in file")

    # Determine date range
    dates = [r.week_date for r in all_records]
    date_start = min(dates) if dates else None
    date_end = max(dates) if dates else None

    # Build dataset
    dataset = InventoryDataset(
        dataset_id=dataset_id,
        name=dataset_name,
        created_at=datetime.utcnow(),
        source_files=[path.name],
        date_range_start=date_start,
        date_range_end=date_end,
        items_count=len(items_dict),
        weeks_count=len(set(r.week_date for r in all_records)),
        items=items_dict,
        records=all_records,
    )

    logger.info(
        f"Parsed {len(items_dict)} items with {len(all_records)} records "
        f"from {date_start} to {date_end}"
    )

    return dataset, warnings


def _parse_sheet(
    xls: pd.ExcelFile,
    sheet_name: str,
) -> Tuple[List[WeeklyRecord], Dict[str, Item], List[str]]:
    """Parse a single sheet from the Excel file."""
    warnings = []

    # Read with header rows skipped (format-specific)
    df = pd.read_excel(xls, sheet_name=sheet_name, skiprows=4)

    # Rename columns based on position (adjust for your format)
    if len(df.columns) < 10:
        warnings.append(f"Sheet '{sheet_name}' has unexpected column count")
        return [], {}, warnings

    # Map columns by position
    col_map = {
        df.columns[0]: 'item_name',
        df.columns[7]: 'on_hand',
        df.columns[9]: 'usage',
    }
    df = df.rename(columns=col_map)

    # Extract week date from sheet name or header
    week_date = _extract_week_date(sheet_name)
    if not week_date:
        warnings.append(f"Could not extract date from sheet '{sheet_name}'")

    # Clean data
    df = df.dropna(subset=['item_name'])
    df = df[~df['item_name'].str.contains('TOTAL', case=False, na=False)]

    records = []
    items = {}

    for _, row in df.iterrows():
        item_name = str(row['item_name']).strip()
        if not item_name:
            continue

        # Generate item ID
        item_id = _generate_item_id(item_name)

        # Create item if new
        if item_id not in items:
            category = _infer_category(item_name)
            vendor = _infer_vendor(item_name)

            items[item_id] = Item(
                item_id=item_id,
                display_name=item_name,
                category=category,
                vendor=vendor,
            )

        # Create record
        try:
            on_hand = float(row.get('on_hand', 0) or 0)
            usage = float(row.get('usage', 0) or 0)

            if usage < 0:
                warnings.append(f"Negative usage for {item_name}: {usage}")

            records.append(WeeklyRecord(
                item_id=item_id,
                week_date=week_date,
                on_hand=on_hand,
                usage=usage,
                week_name=sheet_name,
                source_file=xls.io if hasattr(xls, 'io') else None,
            ))
        except (ValueError, TypeError) as e:
            warnings.append(f"Invalid data for {item_name}: {e}")

    return records, items, warnings


def _extract_week_date(sheet_name: str) -> Optional[datetime]:
    """Extract week date from sheet name."""
    # Try various date patterns
    patterns = [
        r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})',  # M/D/Y or M-D-Y
        r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',     # Y-M-D
        r'Week\s+(\d+)',                          # Week N
    ]

    for pattern in patterns:
        match = re.search(pattern, sheet_name)
        if match:
            try:
                groups = match.groups()
                if len(groups) == 3:
                    # Date pattern
                    if len(groups[0]) == 4:
                        return datetime(int(groups[0]), int(groups[1]), int(groups[2])).date()
                    else:
                        year = int(groups[2])
                        if year < 100:
                            year += 2000
                        return datetime(year, int(groups[0]), int(groups[1])).date()
            except ValueError:
                continue

    return None


def _generate_item_id(item_name: str) -> str:
    """Generate a stable item ID from name."""
    # Normalize: uppercase, remove extra spaces
    normalized = ' '.join(item_name.upper().split())
    return normalized


def _infer_category(item_name: str) -> Category:
    """Infer category from item name."""
    name_lower = item_name.lower()

    category_keywords = {
        Category.WHISKEY: ['whiskey', 'bourbon', 'rye', 'buffalo trace', 'makers mark', 'jack daniel', 'jameson', 'crown royal'],
        Category.VODKA: ['vodka', 'tito', 'grey goose', 'ketel', 'absolut', 'smirnoff'],
        Category.GIN: ['gin', 'tanqueray', 'bombay', 'hendrick'],
        Category.TEQUILA: ['tequila', 'patron', 'casamigos', 'don julio', 'margarita'],
        Category.RUM: ['rum', 'bacardi', 'captain morgan', 'malibu'],
        Category.SCOTCH: ['scotch', 'johnnie walker', 'glenfiddich', 'macallan'],
        Category.BRANDY: ['brandy', 'cognac', 'hennessy', 'remy'],
        Category.WINE: ['wine', 'chardonnay', 'cabernet', 'merlot', 'pinot'],
        Category.DRAFT_BEER: ['draft', 'keg'],
        Category.BOTTLED_BEER: ['beer', 'lager', 'ale', 'ipa', 'corona', 'modelo', 'bud'],
        Category.LIQUEUR: ['liqueur', 'kahlua', 'baileys', 'amaretto'],
        Category.WELL: ['well'],
    }

    for category, keywords in category_keywords.items():
        if any(kw in name_lower for kw in keywords):
            return category

    return Category.UNKNOWN


def _infer_vendor(item_name: str) -> Vendor:
    """Infer vendor from item name (placeholder - should use vendor_map.json)."""
    # This would be replaced with actual vendor mapping lookup
    return Vendor.UNKNOWN


def parse_sales_mix_csv(file_path: str) -> pd.DataFrame:
    """
    Parse a GEMpos sales mix CSV file.

    Returns DataFrame with sales quantities by item.
    """
    # Implementation moved from utils/sales_mix_parser.py
    df = pd.read_csv(file_path)

    # GEMpos format parsing logic
    # ... (existing logic from sales_mix_parser.py)

    return df
