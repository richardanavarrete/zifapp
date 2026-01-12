# Agent Refactor Plan: From Analytics App to Agentic Ordering System

## Current State Analysis

**Your data flow:**
1. Upload Excel → Parse sheets → Create `full_df` (Item, Usage, End Inventory, Date, Week)
2. Group by Item → Compute metrics → Create `summary_df`
3. Apply vendor/category filters → Display in UI
4. Manual worksheet editing → Calculate order quantities

**Critical finding:** Item names like `"WHISKEY Buffalo Trace"` are your only identifier. They're stable enough (you have working vendor/category maps), so we can use them as primary keys for now.

---

## Phase 1: Agent-Ready Architecture (10 Commits)

### Commit 1: Create `models.py` - Normalized Data Model

**Purpose:** Stop letting "sheet shape" drive logic. Create canonical data structures.

**File:** `models.py`

```python
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
        return self.items.get(item_id.strip())

    def get_item_records(self, item_id: str) -> pd.DataFrame:
        """Get all weekly records for a specific item."""
        return self.records[self.records['item_id'] == item_id.strip()].copy()

    def get_unique_items(self) -> List[str]:
        """Get list of all item IDs."""
        return list(self.items.keys())

def create_dataset_from_excel(uploaded_files) -> InventoryDataset:
    """
    Convert uploaded Excel files into InventoryDataset.

    This replaces the inline logic from load_and_process_data().
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

    # Combine all records
    full_df = pd.concat(compiled_records, ignore_index=True)
    full_df = full_df.dropna(subset=['Item', 'Usage'])
    full_df['Item'] = full_df['Item'].astype(str).str.strip()
    full_df = full_df[~full_df['Item'].str.upper().str.startswith('TOTAL')]

    full_df['Usage'] = pd.to_numeric(full_df['Usage'], errors='coerce')
    full_df['End Inventory'] = pd.to_numeric(full_df['End Inventory'], errors='coerce')
    full_df = full_df.dropna(subset=['Usage', 'End Inventory'])

    # Remove duplicates (keep last occurrence)
    full_df = full_df.drop_duplicates(subset=['Item', 'Date'], keep='last')
    full_df = full_df.sort_values(by=['Item', 'Date'])

    # Build items dictionary (will be populated by mappings module)
    unique_items = full_df['Item'].unique()
    items = {item_id: Item(item_id=item_id, display_name=item_id,
                           category="Unknown", vendor="Unknown")
             for item_id in unique_items}

    # Build records dataframe
    records_df = full_df.rename(columns={
        'Item': 'item_id',
        'Date': 'week_date',
        'End Inventory': 'on_hand',
        'Usage': 'usage',
        'Week': 'week_name',
        'Source File': 'source_file'
    })[['item_id', 'week_date', 'on_hand', 'usage', 'week_name', 'source_file']]

    return InventoryDataset(items=items, records=records_df)
```

**Changes:**
- Extract Excel parsing logic from `zifapp.py`
- Create clean data structures
- Item becomes a first-class entity (not just a string in a dataframe)

---

### Commit 2: Create `mappings.py` - Extract Vendor/Category Logic

**Purpose:** Centralize all vendor/category/location mapping logic.

**File:** `mappings.py`

```python
import json
from typing import Dict, List
from models import Item, InventoryDataset

# Vendor mapping (currently hardcoded in zifapp.py lines 166-172)
VENDOR_MAP = {
    "Breakthru": ["WHISKEY Buffalo Trace", "WHISKEY Bulleit Straight Rye", ...],
    "Southern": ["WHISKEY Basil Hayden", ...],
    "RNDC": ["WHISKEY Four Roses", ...],
    "Crescent": ["BEER DFT Alaskan Amber", ...],
    "Hensley": ["BEER DFT Bud Light", ...]
}

def load_vendor_map() -> Dict[str, List[str]]:
    """Load vendor mappings (could be from JSON later)."""
    return {vendor: [item.strip() for item in items]
            for vendor, items in VENDOR_MAP.items()}

def get_vendor_for_item(item_id: str) -> str:
    """Get vendor for a given item."""
    vendor_map = load_vendor_map()
    for vendor, items in vendor_map.items():
        if item_id in items:
            return vendor
    return "Unknown"

def get_category_for_item(item_id: str) -> str:
    """Determine category based on item name patterns."""
    upper_item = item_id.upper().strip()

    if "WELL" in upper_item: return "Well"
    elif "WHISKEY" in upper_item: return "Whiskey"
    elif "VODKA" in upper_item: return "Vodka"
    elif "GIN" in upper_item: return "Gin"
    elif "TEQUILA" in upper_item: return "Tequila"
    elif "RUM" in upper_item: return "Rum"
    elif "SCOTCH" in upper_item: return "Scotch"
    elif "LIQ" in upper_item and "SCHNAPPS" not in upper_item: return "Liqueur"
    elif "SCHNAPPS" in upper_item: return "Cordials"
    elif "WINE" in upper_item: return "Wine"
    elif "BEER DFT" in upper_item: return "Draft Beer"
    elif "BEER BTL" in upper_item: return "Bottled Beer"
    elif "JUICE" in upper_item: return "Juice"
    elif "BAR CONS" in upper_item: return "Bar Consumables"
    return "Unknown"

def load_inventory_layout() -> Dict[str, List[str]]:
    """Load physical location mapping from inventory_layout.json."""
    try:
        with open('inventory_layout.json', 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def get_location_for_item(item_id: str) -> str:
    """Get physical storage location for an item."""
    layout = load_inventory_layout()
    for location, items in layout.items():
        if item_id in items:
            return location
    return "Unknown"

def enrich_dataset(dataset: InventoryDataset) -> InventoryDataset:
    """
    Add vendor, category, and location metadata to all items.

    This replaces the inline mapping logic from zifapp.py.
    """
    for item_id, item in dataset.items.items():
        item.vendor = get_vendor_for_item(item_id)
        item.category = get_category_for_item(item_id)
        item.location = get_location_for_item(item_id)

    return dataset

def get_items_by_vendor(dataset: InventoryDataset, vendor: str) -> List[str]:
    """Get all item IDs for a given vendor."""
    return [item_id for item_id, item in dataset.items.items()
            if item.vendor == vendor]

def get_items_by_category(dataset: InventoryDataset, category: str) -> List[str]:
    """Get all item IDs for a given category."""
    return [item_id for item_id, item in dataset.items.items()
            if item.category == category]
```

**Changes:**
- Extract vendor mapping from zifapp.py:166-172
- Extract category logic from zifapp.py:178-194
- Load inventory_layout.json
- Make it easy to filter by vendor/category

---

### Commit 3: Create `features.py` - Feature Pipeline

**Purpose:** Turn compute_metrics() into a reusable feature pipeline.

**File:** `features.py`

```python
import pandas as pd
import numpy as np
from statsmodels.tsa.holtwinters import SimpleExpSmoothing
from models import InventoryDataset
from typing import Optional

def compute_features(
    dataset: InventoryDataset,
    smoothing_level: float = 0.3,
    trend_threshold: float = 0.1
) -> pd.DataFrame:
    """
    Compute item-level features for agent decision-making.

    This replaces compute_metrics() from zifapp.py:93-153.

    Returns:
        DataFrame with columns:
        - item_id
        - on_hand
        - last_week_usage
        - avg_ytd, avg_10wk, avg_4wk, avg_2wk
        - avg_highest_4, avg_lowest_4_nonzero
        - volatility (std/mean)
        - weeks_on_hand_ytd, weeks_on_hand_10wk, weeks_on_hand_4wk
        - trend (↑→↓)
        - recent_trend_ratio (last 4 weeks vs prior 4 weeks)
        - anomaly_negative_usage, anomaly_huge_jump, anomaly_missing_count
    """

    def compute_item_features(group):
        usage = group['usage']
        inventory = group['on_hand']
        dates = group['week_date']

        # Basic stats
        last_week_usage = usage.iloc[-1] if not usage.empty else None
        last_10 = usage.tail(10)
        last_4 = usage.tail(4)
        last_2 = usage.tail(2)

        # YTD based on most recent year in data
        if pd.api.types.is_datetime64_any_dtype(dates) and not dates.empty:
            most_recent_year = dates.max().year
            ytd_avg = group[dates.dt.year == most_recent_year]['usage'].mean()
        else:
            ytd_avg = None

        # Volatility
        volatility = usage.std() / usage.mean() if usage.mean() > 0 else None

        # Highest/Lowest averages
        avg_highest_4 = usage.nlargest(4).mean() if not usage.empty else None
        non_zero_usage = usage[usage > 0]
        avg_lowest_4_nonzero = non_zero_usage.nsmallest(4).mean() if not non_zero_usage.empty else None

        # Weeks on hand calculations
        def safe_div(n, d):
            if pd.notna(d) and d > 0:
                return round(n / d, 2)
            return None

        on_hand_val = inventory.iloc[-1]
        weeks_on_hand_ytd = safe_div(on_hand_val, ytd_avg)
        weeks_on_hand_10wk = safe_div(on_hand_val, last_10.mean())
        weeks_on_hand_4wk = safe_div(on_hand_val, last_4.mean())
        weeks_on_hand_2wk = safe_div(on_hand_val, last_2.mean())

        # Trend indicator using exponential smoothing
        trend = "→"
        if len(usage) >= 4:
            try:
                model = SimpleExpSmoothing(usage.values).fit(
                    smoothing_level=smoothing_level,
                    optimized=False
                )
                smoothed_current = model.fittedvalues[-1]
                baseline = usage.mean()
                if baseline > 0:
                    ratio = smoothed_current / baseline
                    if ratio > (1 + trend_threshold):
                        trend = "↑"
                    elif ratio < (1 - trend_threshold):
                        trend = "↓"
            except Exception:
                trend = "→"

        # Recent trend ratio (last 4 vs prior 4)
        recent_trend_ratio = None
        if len(usage) >= 8:
            recent_4 = usage.tail(4).mean()
            prior_4 = usage.tail(8).head(4).mean()
            if prior_4 > 0:
                recent_trend_ratio = recent_4 / prior_4

        # Anomaly detection
        anomaly_negative_usage = (usage < 0).any()
        anomaly_huge_jump = False
        if len(usage) >= 2:
            mean_val = usage.mean()
            if mean_val > 0:
                anomaly_huge_jump = ((usage.iloc[-1] / mean_val) > 5)

        anomaly_missing_count = len(usage) < 4

        return pd.Series({
            'on_hand': round(on_hand_val, 2),
            'last_week_usage': round(last_week_usage, 2) if pd.notna(last_week_usage) else None,
            'avg_ytd': round(ytd_avg, 2) if pd.notna(ytd_avg) else None,
            'avg_10wk': round(last_10.mean(), 2) if not last_10.empty else None,
            'avg_4wk': round(last_4.mean(), 2) if not last_4.empty else None,
            'avg_2wk': round(last_2.mean(), 2) if not last_2.empty else None,
            'avg_highest_4': round(avg_highest_4, 2) if pd.notna(avg_highest_4) else None,
            'avg_lowest_4_nonzero': round(avg_lowest_4_nonzero, 2) if pd.notna(avg_lowest_4_nonzero) else None,
            'volatility': round(volatility, 2) if pd.notna(volatility) else None,
            'weeks_on_hand_ytd': weeks_on_hand_ytd,
            'weeks_on_hand_10wk': weeks_on_hand_10wk,
            'weeks_on_hand_4wk': weeks_on_hand_4wk,
            'weeks_on_hand_2wk': weeks_on_hand_2wk,
            'trend': trend,
            'recent_trend_ratio': round(recent_trend_ratio, 2) if pd.notna(recent_trend_ratio) else None,
            'anomaly_negative_usage': anomaly_negative_usage,
            'anomaly_huge_jump': anomaly_huge_jump,
            'anomaly_missing_count': anomaly_missing_count,
        })

    features_df = dataset.records.groupby('item_id').apply(compute_item_features).reset_index()
    return features_df
```

**Changes:**
- Extract compute_metrics from zifapp.py:93-153
- Add volatility calculation
- Add anomaly flags (for agent to detect issues)
- Add recent trend ratio (for agent to use in decisions)

---

### Commit 4: Create `policy.py` - Rules-Based Decision Engine

**Purpose:** This is the "agent brain v0" - makes ordering decisions without AI.

**File:** `policy.py`

```python
import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass
from models import InventoryDataset
import mappings

@dataclass
class OrderTargets:
    """Configuration for ordering targets."""
    # Default target weeks by category
    target_weeks_by_category: Dict[str, float] = None

    # Item-specific overrides
    item_overrides: Dict[str, float] = None

    # Items to never order
    never_order: List[str] = None

    def __post_init__(self):
        if self.target_weeks_by_category is None:
            self.target_weeks_by_category = {
                "Draft Beer": 2.0,
                "Bottled Beer": 2.5,
                "Whiskey": 4.0,
                "Vodka": 4.0,
                "Gin": 5.0,
                "Tequila": 4.0,
                "Rum": 5.0,
                "Scotch": 6.0,
                "Well": 3.0,
                "Liqueur": 6.0,
                "Cordials": 8.0,
                "Wine": 3.0,
                "Juice": 2.0,
                "Bar Consumables": 3.0,
            }
        if self.item_overrides is None:
            self.item_overrides = {}
        if self.never_order is None:
            self.never_order = []

    def get_target_weeks(self, item_id: str, category: str) -> float:
        """Get target weeks for an item."""
        if item_id in self.item_overrides:
            return self.item_overrides[item_id]
        return self.target_weeks_by_category.get(category, 4.0)

@dataclass
class OrderConstraints:
    """Constraints for ordering."""
    max_total_spend: Optional[float] = None
    max_total_cases: Optional[int] = None
    vendor_minimums: Dict[str, float] = None

    def __post_init__(self):
        if self.vendor_minimums is None:
            self.vendor_minimums = {}

@dataclass
class Recommendation:
    """A single item order recommendation."""
    item_id: str
    vendor: str
    category: str
    on_hand: float
    avg_usage: float
    weeks_on_hand: float
    target_weeks: float
    recommended_qty: int
    reason_codes: List[str]
    confidence: str  # high/medium/low
    notes: str

def recommend_order(
    dataset: InventoryDataset,
    features_df: pd.DataFrame,
    targets: OrderTargets,
    constraints: OrderConstraints,
    usage_column: str = 'avg_4wk'  # Which average to use
) -> pd.DataFrame:
    """
    Generate order recommendations.

    Returns DataFrame with columns:
    - item_id, vendor, category
    - on_hand, avg_usage, weeks_on_hand, target_weeks
    - recommended_qty
    - reason_codes (list of strings)
    - confidence (high/medium/low)
    - notes (plain text)
    """

    recommendations = []

    for _, row in features_df.iterrows():
        item_id = row['item_id']
        item = dataset.get_item(item_id)

        if not item:
            continue

        # Skip items flagged as never order
        if item_id in targets.never_order:
            continue

        # Get target weeks for this item
        target_weeks = targets.get_target_weeks(item_id, item.category)

        # Get usage metric
        avg_usage = row.get(usage_column, row.get('avg_4wk', 0))
        if pd.isna(avg_usage) or avg_usage <= 0:
            avg_usage = 0

        on_hand = row['on_hand']
        weeks_on_hand = on_hand / avg_usage if avg_usage > 0 else 999

        # Calculate order quantity
        target_inventory = target_weeks * avg_usage
        order_qty = int(max(0, target_inventory - on_hand))

        # Round to cases if case_size is known
        if item.case_size and order_qty > 0:
            order_qty = ((order_qty + item.case_size - 1) // item.case_size) * item.case_size

        # Determine reason codes
        reason_codes = []
        confidence = "high"
        notes = ""

        if weeks_on_hand < 1.0:
            reason_codes.append("STOCKOUT_RISK")
            notes += "Critical: Less than 1 week of inventory. "
        elif weeks_on_hand < target_weeks * 0.5:
            reason_codes.append("LOW_STOCK")
            notes += "Below 50% of target weeks. "

        if weeks_on_hand > target_weeks * 2:
            reason_codes.append("OVERSTOCK")
            notes += "Inventory exceeds 2x target. "
            order_qty = 0  # Don't order if overstocked

        if row.get('volatility', 0) > 1.0:
            reason_codes.append("VOLATILE")
            confidence = "medium"
            notes += "High volatility in usage. "

        if row.get('anomaly_negative_usage', False):
            reason_codes.append("DATA_ISSUE_NEGATIVE")
            confidence = "low"
            notes += "Negative usage detected. Check counts. "

        if row.get('anomaly_huge_jump', False):
            reason_codes.append("DATA_ISSUE_JUMP")
            confidence = "medium"
            notes += "Usage jumped >5x average. Verify count. "

        if row.get('anomaly_missing_count', False):
            reason_codes.append("INSUFFICIENT_DATA")
            confidence = "low"
            notes += "Less than 4 weeks of data. "

        if row.get('trend') == '↑':
            reason_codes.append("TRENDING_UP")
            notes += "Usage trending upward. "
        elif row.get('trend') == '↓':
            reason_codes.append("TRENDING_DOWN")
            notes += "Usage trending downward. "

        if not reason_codes:
            reason_codes.append("ROUTINE_RESTOCK")

        recommendations.append({
            'item_id': item_id,
            'vendor': item.vendor,
            'category': item.category,
            'on_hand': on_hand,
            'avg_usage': avg_usage,
            'weeks_on_hand': round(weeks_on_hand, 1),
            'target_weeks': target_weeks,
            'recommended_qty': order_qty,
            'reason_codes': reason_codes,
            'confidence': confidence,
            'notes': notes.strip()
        })

    rec_df = pd.DataFrame(recommendations)

    # Sort: prioritize stockout risks, then by vendor
    rec_df['_priority'] = rec_df['reason_codes'].apply(
        lambda codes: 0 if 'STOCKOUT_RISK' in codes else
                     1 if 'LOW_STOCK' in codes else 2
    )
    rec_df = rec_df.sort_values(['_priority', 'vendor', 'category', 'item_id'])
    rec_df = rec_df.drop(columns=['_priority'])

    return rec_df
```

**Changes:**
- New rules-based decision engine
- Returns structured recommendations (not just UI)
- Includes confidence scores and reason codes
- Handles anomalies and data issues

---

### Commit 5: Create `storage.py` - Persistence Layer

**Purpose:** Add memory so agent can learn over time.

**File:** `storage.py`

```python
import sqlite3
import json
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import contextmanager

DB_PATH = "agent_memory.db"

@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Initialize the database schema."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Agent runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_runs (
                run_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                dataset_hash TEXT,
                usage_column TEXT,
                total_items INTEGER,
                items_to_order INTEGER,
                total_qty_recommended INTEGER,
                summary TEXT
            )
        """)

        # Agent recommendations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_recs (
                rec_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                vendor TEXT,
                category TEXT,
                on_hand REAL,
                avg_usage REAL,
                weeks_on_hand REAL,
                target_weeks REAL,
                recommended_qty INTEGER,
                reason_codes TEXT,
                confidence TEXT,
                notes TEXT,
                FOREIGN KEY (run_id) REFERENCES agent_runs (run_id)
            )
        """)

        # Agent actions (user approvals/edits) table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_actions (
                action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                recommended_qty INTEGER,
                approved_qty INTEGER,
                user_override_reason TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES agent_runs (run_id)
            )
        """)

        # User preferences table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_prefs (
                pref_id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id TEXT UNIQUE,
                target_weeks_override REAL,
                never_order INTEGER DEFAULT 0,
                preferred_case_rounding INTEGER,
                notes TEXT,
                last_updated TEXT NOT NULL
            )
        """)

        conn.commit()

def save_agent_run(
    run_id: str,
    recommendations_df: pd.DataFrame,
    summary: str,
    usage_column: str = 'avg_4wk'
):
    """Save an agent run and its recommendations."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Save run summary
        cursor.execute("""
            INSERT INTO agent_runs (
                run_id, timestamp, usage_column,
                total_items, items_to_order, total_qty_recommended, summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            datetime.now().isoformat(),
            usage_column,
            len(recommendations_df),
            len(recommendations_df[recommendations_df['recommended_qty'] > 0]),
            recommendations_df['recommended_qty'].sum(),
            summary
        ))

        # Save individual recommendations
        for _, row in recommendations_df.iterrows():
            cursor.execute("""
                INSERT INTO agent_recs (
                    run_id, item_id, vendor, category,
                    on_hand, avg_usage, weeks_on_hand, target_weeks,
                    recommended_qty, reason_codes, confidence, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id,
                row['item_id'],
                row['vendor'],
                row['category'],
                row['on_hand'],
                row['avg_usage'],
                row['weeks_on_hand'],
                row['target_weeks'],
                row['recommended_qty'],
                json.dumps(row['reason_codes']),
                row['confidence'],
                row['notes']
            ))

        conn.commit()

def save_user_actions(run_id: str, actions: List[Dict]):
    """
    Save user actions (approvals/edits) for a run.

    actions: List of dicts with keys: item_id, recommended_qty, approved_qty, user_override_reason
    """
    with get_db() as conn:
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()

        for action in actions:
            cursor.execute("""
                INSERT INTO agent_actions (
                    run_id, item_id, recommended_qty, approved_qty,
                    user_override_reason, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                run_id,
                action['item_id'],
                action['recommended_qty'],
                action['approved_qty'],
                action.get('user_override_reason', ''),
                timestamp
            ))

        conn.commit()

def get_user_prefs() -> Dict[str, Dict]:
    """Get all user preferences as a dictionary."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_prefs")
        rows = cursor.fetchall()

        prefs = {}
        for row in rows:
            item_id = row[1]
            prefs[item_id] = {
                'target_weeks_override': row[2],
                'never_order': bool(row[3]),
                'preferred_case_rounding': row[4],
                'notes': row[5]
            }
        return prefs

def save_user_pref(item_id: str, **kwargs):
    """Save a user preference for an item."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Check if pref exists
        cursor.execute("SELECT pref_id FROM user_prefs WHERE item_id = ?", (item_id,))
        existing = cursor.fetchone()

        if existing:
            # Update existing
            set_clauses = []
            values = []
            for key, val in kwargs.items():
                set_clauses.append(f"{key} = ?")
                values.append(val)
            set_clauses.append("last_updated = ?")
            values.append(datetime.now().isoformat())
            values.append(item_id)

            sql = f"UPDATE user_prefs SET {', '.join(set_clauses)} WHERE item_id = ?"
            cursor.execute(sql, values)
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO user_prefs (
                    item_id, target_weeks_override, never_order,
                    preferred_case_rounding, notes, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                item_id,
                kwargs.get('target_weeks_override'),
                kwargs.get('never_order', 0),
                kwargs.get('preferred_case_rounding'),
                kwargs.get('notes', ''),
                datetime.now().isoformat()
            ))

        conn.commit()

def get_recent_runs(limit: int = 10) -> pd.DataFrame:
    """Get recent agent runs."""
    with get_db() as conn:
        return pd.read_sql_query(
            "SELECT * FROM agent_runs ORDER BY timestamp DESC LIMIT ?",
            conn,
            params=(limit,)
        )

def get_run_details(run_id: str) -> pd.DataFrame:
    """Get detailed recommendations for a specific run."""
    with get_db() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM agent_recs WHERE run_id = ?",
            conn,
            params=(run_id,)
        )
        # Parse reason_codes back from JSON
        df['reason_codes'] = df['reason_codes'].apply(json.loads)
        return df
```

**Changes:**
- SQLite database for persistence
- Tables for runs, recommendations, user actions, preferences
- Functions to save/load agent memory

---

### Commit 6: Create `agent.py` - Orchestrator

**Purpose:** Tie everything together in an "agent run" workflow.

**File:** `agent.py`

```python
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
from models import InventoryDataset
from features import compute_features
from policy import recommend_order, OrderTargets, OrderConstraints
from storage import save_agent_run, get_user_prefs, init_db
import mappings
import hashlib

def generate_run_id(dataset: InventoryDataset) -> str:
    """Generate a unique run ID based on dataset and timestamp."""
    timestamp = datetime.now().isoformat()
    hash_input = f"{timestamp}_{len(dataset.records)}".encode()
    short_hash = hashlib.md5(hash_input).hexdigest()[:8]
    return f"run_{short_hash}"

def run_agent(
    dataset: InventoryDataset,
    usage_column: str = 'avg_4wk',
    smoothing_level: float = 0.3,
    trend_threshold: float = 0.1
) -> Dict:
    """
    Execute a complete agent run.

    Steps:
    1. Enrich dataset with mappings
    2. Compute features
    3. Load user preferences
    4. Generate recommendations
    5. Save run to storage
    6. Return results

    Returns:
        {
            'run_id': str,
            'recommendations': pd.DataFrame,
            'summary': str,
            'items_needing_recount': List[str],
            'dataset': InventoryDataset,
            'features': pd.DataFrame
        }
    """

    # Ensure database is initialized
    init_db()

    # Step 1: Enrich dataset
    dataset = mappings.enrich_dataset(dataset)

    # Step 2: Compute features
    features_df = compute_features(
        dataset,
        smoothing_level=smoothing_level,
        trend_threshold=trend_threshold
    )

    # Step 3: Load user preferences
    user_prefs = get_user_prefs()

    # Build targets from preferences
    targets = OrderTargets()
    for item_id, prefs in user_prefs.items():
        if prefs.get('target_weeks_override'):
            targets.item_overrides[item_id] = prefs['target_weeks_override']
        if prefs.get('never_order'):
            targets.never_order.append(item_id)

    # Step 4: Generate recommendations
    constraints = OrderConstraints()
    recommendations_df = recommend_order(
        dataset,
        features_df,
        targets,
        constraints,
        usage_column=usage_column
    )

    # Step 5: Identify items needing recount
    items_needing_recount = []
    for _, row in recommendations_df.iterrows():
        reason_codes = row['reason_codes']
        if any(code.startswith('DATA_ISSUE') for code in reason_codes):
            items_needing_recount.append(row['item_id'])

    # Step 6: Generate summary
    total_items = len(recommendations_df)
    items_to_order = len(recommendations_df[recommendations_df['recommended_qty'] > 0])
    total_qty = recommendations_df['recommended_qty'].sum()

    summary = f"Total items: {total_items} | To order: {items_to_order} | Total qty: {total_qty}"

    # Step 7: Save run
    run_id = generate_run_id(dataset)
    save_agent_run(run_id, recommendations_df, summary, usage_column)

    return {
        'run_id': run_id,
        'recommendations': recommendations_df,
        'summary': summary,
        'items_needing_recount': items_needing_recount,
        'dataset': dataset,
        'features': features_df
    }
```

**Changes:**
- Single function that orchestrates the entire agent workflow
- Returns structured output
- Automatically flags data issues
- Persists results

---

### Commit 7: Refactor `zifapp.py` to Use New Architecture

**Purpose:** Gut the monolithic app, use the new modules.

**Changes to `zifapp.py`:**

```python
import streamlit as st
import pandas as pd
from datetime import datetime

# NEW: Import our modules
from models import create_dataset_from_excel
from agent import run_agent
from storage import get_recent_runs, save_user_actions, init_db
from mappings import get_items_by_vendor, get_items_by_category

# Initialize database on app start
init_db()

st.set_page_config(page_title="Bev Usage Analyzer", layout="wide")
st.title("🍺 Bev Usage Analyzer")

# --- NEW: Simplified caching ---
@st.cache_data
def load_and_process_data(uploaded_files, smoothing_level=0.3, trend_threshold=0.1):
    """
    Load data using new models module.
    """
    dataset = create_dataset_from_excel(uploaded_files)
    return dataset

# --- File Upload (unchanged) ---
uploaded_files = st.file_uploader(
    "Upload your BEVWEEKLY Excel Files",
    type="xlsx",
    accept_multiple_files=True
)

if uploaded_files:
    # Show file summary (unchanged)
    st.info(f"**{len(uploaded_files)} file(s) uploaded**")

    with st.expander("Trend Settings", expanded=False):
        smoothing_level = st.slider("Smoothing Level (α)", 0.1, 0.9, 0.3, 0.05)
        trend_threshold = st.slider("Trend Threshold", 0.05, 0.30, 0.10, 0.05)

    # Load dataset
    dataset = load_and_process_data(uploaded_files, smoothing_level, trend_threshold)

    # NEW: Add Agent tab
    tab_agent, tab_summary, tab_ordering_worksheet, tab_sales_mix, tab_trends = st.tabs([
        "🤖 Agent", "📊 Summary", "🧪 Ordering Worksheet", "Sales Mix Analysis", "📈 Item Trends"
    ])

    # --- NEW TAB: AGENT ---
    with tab_agent:
        st.subheader("🤖 Weekly Order Agent")
        st.markdown("""
        The agent analyzes your inventory and generates a draft order based on:
        - Target weeks of supply by category
        - Current stock levels and usage trends
        - Data quality checks (flags items needing recount)
        """)

        col1, col2 = st.columns([2, 1])
        with col1:
            usage_option = st.selectbox(
                "Select usage average:",
                options=['avg_4wk', 'avg_10wk', 'avg_2wk', 'avg_ytd'],
                format_func=lambda x: {
                    'avg_4wk': '4-Week Average',
                    'avg_10wk': '10-Week Average',
                    'avg_2wk': '2-Week Average',
                    'avg_ytd': 'Year-to-Date Average'
                }[x],
                index=0
            )

        with col2:
            st.write("")
            st.write("")
            if st.button("🚀 Run Agent", type="primary", use_container_width=True):
                with st.spinner("Running agent..."):
                    agent_result = run_agent(
                        dataset,
                        usage_column=usage_option,
                        smoothing_level=smoothing_level,
                        trend_threshold=trend_threshold
                    )
                    st.session_state['agent_result'] = agent_result
                    st.success("✅ Agent run complete!")

        # Show results if available
        if 'agent_result' in st.session_state:
            result = st.session_state['agent_result']

            st.markdown("---")
            st.markdown(f"**Run ID:** `{result['run_id']}`")
            st.markdown(f"**Summary:** {result['summary']}")

            # Items needing recount
            if result['items_needing_recount']:
                with st.expander("⚠️ Items Needing Recount", expanded=True):
                    st.warning(f"{len(result['items_needing_recount'])} items flagged for recount")
                    for item in result['items_needing_recount']:
                        st.write(f"- {item}")

            # Recommendations table
            st.markdown("### Draft Order Recommendations")

            recs_df = result['recommendations']

            # Filter to items with recommended qty > 0
            view_option = st.radio(
                "View:",
                ["Items to Order", "All Items", "By Vendor"],
                horizontal=True
            )

            if view_option == "Items to Order":
                display_df = recs_df[recs_df['recommended_qty'] > 0]
            elif view_option == "All Items":
                display_df = recs_df
            else:  # By Vendor
                vendor_filter = st.selectbox("Select Vendor:", recs_df['vendor'].unique())
                display_df = recs_df[recs_df['vendor'] == vendor_filter]

            # Editable dataframe for approval
            edited_df = st.data_editor(
                display_df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "item_id": st.column_config.TextColumn("Item", disabled=True),
                    "vendor": st.column_config.TextColumn("Vendor", disabled=True),
                    "category": st.column_config.TextColumn("Category", disabled=True),
                    "on_hand": st.column_config.NumberColumn("On Hand", format="%.2f", disabled=True),
                    "avg_usage": st.column_config.NumberColumn("Avg Usage", format="%.2f", disabled=True),
                    "weeks_on_hand": st.column_config.NumberColumn("Weeks Left", format="%.1f", disabled=True),
                    "target_weeks": st.column_config.NumberColumn("Target Weeks", format="%.1f", disabled=True),
                    "recommended_qty": st.column_config.NumberColumn("Recommended Qty", min_value=0, step=1),
                    "confidence": st.column_config.TextColumn("Confidence", disabled=True),
                    "notes": st.column_config.TextColumn("Notes", disabled=True),
                }
            )

            # Approval buttons
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("✅ Approve & Save Order", use_container_width=True):
                    # Save user actions
                    actions = []
                    for _, row in edited_df.iterrows():
                        actions.append({
                            'item_id': row['item_id'],
                            'recommended_qty': row['recommended_qty'],
                            'approved_qty': row['recommended_qty'],
                            'user_override_reason': ''
                        })
                    save_user_actions(result['run_id'], actions)
                    st.success("Order saved!")

            with col2:
                # Download CSV
                csv = edited_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Download Order CSV",
                    data=csv,
                    file_name=f"order_{result['run_id']}.csv",
                    use_container_width=True
                )

            # Recent runs history
            with st.expander("📜 Recent Agent Runs", expanded=False):
                recent_runs = get_recent_runs(limit=10)
                if not recent_runs.empty:
                    st.dataframe(recent_runs, use_container_width=True, hide_index=True)

    # --- Keep existing tabs with minimal changes ---
    # (Summary, Ordering Worksheet, Sales Mix, Trends remain mostly the same)
    # Just update them to use dataset.records and dataset.items instead of full_df/summary_df
```

**Changes:**
- Add new Agent tab
- Replace inline logic with module imports
- Keep existing tabs mostly intact
- Add approval flow and run history

---

### Commits 8-10: Polish and Integration

**Commit 8: Wire User Preferences UI**

Add settings panel where users can:
- Set item-specific target weeks
- Mark items as "never order"
- Set preferred case rounding

**Commit 9: Add Export Functionality**

- Export by vendor (separate CSVs)
- Export summary report
- Email integration (optional)

**Commit 10: Testing and Documentation**

- Add example test cases
- Document the new architecture
- Update README with agent workflow

---

## After Phase 1: What You'll Have

✅ **Agent-Ready Architecture:**
- Clean data model (models.py)
- Feature pipeline (features.py)
- Rules-based policy (policy.py)
- Persistence layer (storage.py)
- Agent orchestrator (agent.py)

✅ **Core Agent Features:**
- Generates draft orders automatically
- Flags items needing recount
- Human-in-the-loop approval
- Remembers past runs
- Learns from user edits

✅ **No LLM Yet:**
- All decisions are deterministic
- Fast and reliable
- Easy to debug

---

## Phase 2 Preview: Adding Memory Intelligence

After Phase 1, you'll add:
1. **Learn from overrides:** If user always orders 50% more than agent suggests, adjust
2. **Cooldown tracking:** "We ordered this 2 weeks ago, skip it"
3. **Seasonal patterns:** "This item sells 2x in summer"
4. **Vendor preferences:** "User prefers Breakthru orders on Mondays"

---

## Phase 3 Preview: Adding LLM Explanations

After Phase 2, you'll add:
1. **Item-level "Explain" buttons:** LLM generates natural language explanation
2. **Anomaly descriptions:** "This usage spike coincides with a holiday"
3. **Smart summaries:** "This week's order is 20% higher due to upcoming event"

---

## Next Steps

**Start with Commit 1:** Create `models.py`

Once you have models.py working, the rest follows naturally. Each commit is independent and shippable.

Want me to start implementing? I can:
1. Create all the files
2. Refactor zifapp.py
3. Test the agent workflow
4. Push to your branch

Let me know!
