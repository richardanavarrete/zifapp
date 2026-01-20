"""
Parser Service - Handles spreadsheet parsing

Attempts to auto-detect column mappings and parse any clean inventory sheet.
"""

import re
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any

import pandas as pd

from smallcogs.models.inventory import Item, Record, Dataset, UploadResult


class ParserService:
    """Parses inventory spreadsheets into our data model."""

    # Common column name patterns for auto-detection
    ITEM_PATTERNS = [
        r'^item', r'^product', r'^name', r'^description', r'^sku',
        r'^material', r'^inventory.?item'
    ]
    COUNT_PATTERNS = [
        r'^on.?hand', r'^qty', r'^quantity', r'^count', r'^stock',
        r'^ending', r'^end.?inv', r'^current', r'^balance'
    ]
    USAGE_PATTERNS = [
        r'^usage', r'^used', r'^consumed', r'^sold', r'^movement'
    ]
    CATEGORY_PATTERNS = [
        r'^category', r'^type', r'^group', r'^class', r'^dept'
    ]
    DATE_PATTERNS = [
        r'^date', r'^week', r'^period', r'^time'
    ]
    VENDOR_PATTERNS = [
        r'^vendor', r'^supplier', r'^source'
    ]

    def parse_file(
        self,
        file_path: str,
        dataset_name: Optional[str] = None,
        skip_rows: int = 0,
        sheet_name: Optional[str] = None,
    ) -> Tuple[Dataset, List[str]]:
        """
        Parse an inventory file (Excel or CSV).

        Returns (Dataset, warnings)
        """
        warnings = []
        path = Path(file_path)
        filename = path.name

        # Determine file type and read
        if path.suffix.lower() in ['.xlsx', '.xls']:
            df, sheet_warnings = self._read_excel(file_path, skip_rows, sheet_name)
            warnings.extend(sheet_warnings)
        elif path.suffix.lower() == '.csv':
            df = pd.read_csv(file_path, skiprows=skip_rows)
        else:
            raise ValueError(f"Unsupported file type: {path.suffix}")

        if df.empty:
            raise ValueError("File contains no data")

        # Clean column names
        df.columns = [str(c).strip() for c in df.columns]

        # Auto-detect column mappings
        mapping = self._detect_columns(df)
        if not mapping.get('item'):
            raise ValueError("Could not detect item/product name column")

        # Parse data
        items, records, parse_warnings = self._parse_data(df, mapping, filename)
        warnings.extend(parse_warnings)

        # Build dataset
        dataset_id = f"ds_{uuid.uuid4().hex[:12]}"
        dataset = Dataset(
            dataset_id=dataset_id,
            name=dataset_name or path.stem,
            source_files=[filename],
            items={item.item_id: item for item in items},
            records=records,
            items_count=len(items),
            records_count=len(records),
        )

        # Compute metadata
        if records:
            dates = [r.record_date for r in records]
            dataset.date_range_start = min(dates)
            dataset.date_range_end = max(dates)
            dataset.periods_count = len(set(dates))

        # Extract unique categories/vendors
        dataset.categories = sorted(set(
            i.category for i in items if i.category
        ))
        dataset.vendors = sorted(set(
            i.vendor for i in items if i.vendor
        ))

        return dataset, warnings

    def _read_excel(
        self,
        file_path: str,
        skip_rows: int,
        sheet_name: Optional[str]
    ) -> Tuple[pd.DataFrame, List[str]]:
        """Read Excel file, handling multiple sheets."""
        warnings = []
        xl = pd.ExcelFile(file_path)

        if sheet_name:
            df = xl.parse(sheet_name, skiprows=skip_rows)
        elif len(xl.sheet_names) == 1:
            df = xl.parse(xl.sheet_names[0], skiprows=skip_rows)
        else:
            # Try to find the right sheet
            for name in xl.sheet_names:
                if any(kw in name.lower() for kw in ['inventory', 'data', 'sheet1']):
                    df = xl.parse(name, skiprows=skip_rows)
                    warnings.append(f"Auto-selected sheet: {name}")
                    break
            else:
                df = xl.parse(xl.sheet_names[0], skiprows=skip_rows)
                warnings.append(f"Using first sheet: {xl.sheet_names[0]}")

        return df, warnings

    def _detect_columns(self, df: pd.DataFrame) -> Dict[str, str]:
        """Auto-detect column mappings."""
        mapping = {}
        columns_lower = {c: c.lower() for c in df.columns}

        def find_match(patterns: List[str]) -> Optional[str]:
            for col, col_lower in columns_lower.items():
                for pattern in patterns:
                    if re.search(pattern, col_lower):
                        return col
            return None

        mapping['item'] = find_match(self.ITEM_PATTERNS)
        mapping['on_hand'] = find_match(self.COUNT_PATTERNS)
        mapping['usage'] = find_match(self.USAGE_PATTERNS)
        mapping['category'] = find_match(self.CATEGORY_PATTERNS)
        mapping['date'] = find_match(self.DATE_PATTERNS)
        mapping['vendor'] = find_match(self.VENDOR_PATTERNS)

        return mapping

    def _parse_data(
        self,
        df: pd.DataFrame,
        mapping: Dict[str, str],
        filename: str
    ) -> Tuple[List[Item], List[Record], List[str]]:
        """Parse DataFrame into Items and Records."""
        warnings = []
        items_dict: Dict[str, Item] = {}
        records: List[Record] = []

        # Clean data
        df = df.dropna(subset=[mapping['item']])
        df = df[~df[mapping['item']].astype(str).str.upper().str.contains('TOTAL', na=False)]

        # Default date if not in data
        default_date = date.today()
        if mapping.get('date'):
            try:
                df[mapping['date']] = pd.to_datetime(df[mapping['date']])
            except Exception:
                warnings.append("Could not parse date column, using today's date")
                mapping['date'] = None

        for idx, row in df.iterrows():
            # Get item name
            item_name = str(row[mapping['item']]).strip()
            if not item_name or item_name.lower() == 'nan':
                continue

            # Generate item_id from name
            item_id = self._make_item_id(item_name)

            # Create item if new
            if item_id not in items_dict:
                items_dict[item_id] = Item(
                    item_id=item_id,
                    name=item_name,
                    category=self._safe_get(row, mapping.get('category')),
                    vendor=self._safe_get(row, mapping.get('vendor')),
                )

            # Get record date
            if mapping.get('date'):
                try:
                    record_date = row[mapping['date']].date()
                except Exception:
                    record_date = default_date
            else:
                record_date = default_date

            # Get on_hand
            on_hand = 0.0
            if mapping.get('on_hand'):
                try:
                    on_hand = float(row[mapping['on_hand']])
                except (ValueError, TypeError):
                    pass

            # Get usage
            usage = None
            if mapping.get('usage'):
                try:
                    usage = float(row[mapping['usage']])
                    if usage < 0:
                        warnings.append(f"Negative usage for {item_name}: {usage}")
                except (ValueError, TypeError):
                    pass

            # Create record
            records.append(Record(
                record_id=f"r_{uuid.uuid4().hex[:8]}",
                item_id=item_id,
                record_date=record_date,
                on_hand=on_hand,
                usage=usage,
                source_file=filename,
            ))

        return list(items_dict.values()), records, warnings

    def _make_item_id(self, name: str) -> str:
        """Generate a stable item ID from name."""
        # Simple slugification
        slug = re.sub(r'[^a-zA-Z0-9]+', '_', name.lower()).strip('_')
        return slug[:50]  # Limit length

    def _safe_get(self, row: pd.Series, col: Optional[str]) -> Optional[str]:
        """Safely get a string value from a row."""
        if not col or col not in row.index:
            return None
        val = row[col]
        if pd.isna(val):
            return None
        return str(val).strip() or None
