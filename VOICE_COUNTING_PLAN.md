# Voice Counting Feature - Implementation Plan

## Overview
Add voice-based inventory counting with fuzzy matching, confidence scoring, text log editing, and Excel export ordered to match your physical inventory sheet layout.

## Architecture

### 1. Data Model Extensions

**New Models** (add to `models.py`):

```python
@dataclass
class VoiceCountRecord:
    """Individual item count from voice input"""
    record_id: str              # UUID
    session_id: str             # Links to VoiceCountSession
    timestamp: datetime
    raw_transcript: str         # Original speech-to-text output
    cleaned_transcript: str     # User-edited version
    matched_item_id: Optional[str]  # Matched Item.item_id
    count_value: Optional[float]    # Counted quantity
    confidence_score: float     # 0.0-1.0 fuzzy match confidence
    match_method: str           # "exact", "fuzzy", "manual"
    is_verified: bool           # User confirmed the match
    location: Optional[str]     # Physical location during count
    notes: Optional[str]

@dataclass
class VoiceCountSession:
    """A complete voice counting session"""
    session_id: str             # UUID
    created_at: datetime
    updated_at: datetime
    session_name: str           # "Friday Evening Count", etc.
    status: str                 # "in_progress", "completed", "exported"
    total_items_counted: int
    records: List[VoiceCountRecord]
    inventory_order: List[str]  # item_ids in sheet order for export
```

### 2. Database Schema

**New Tables** (extend `storage.py`):

```sql
CREATE TABLE voice_count_sessions (
    session_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    session_name TEXT NOT NULL,
    status TEXT NOT NULL,
    total_items_counted INTEGER DEFAULT 0,
    inventory_order_json TEXT  -- JSON array of item_ids
);

CREATE TABLE voice_count_records (
    record_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    raw_transcript TEXT NOT NULL,
    cleaned_transcript TEXT,
    matched_item_id TEXT,
    count_value REAL,
    confidence_score REAL NOT NULL,
    match_method TEXT NOT NULL,
    is_verified INTEGER DEFAULT 0,
    location TEXT,
    notes TEXT,
    FOREIGN KEY (session_id) REFERENCES voice_count_sessions(session_id)
);

CREATE INDEX idx_voice_records_session ON voice_count_records(session_id);
CREATE INDEX idx_voice_records_item ON voice_count_records(matched_item_id);
```

### 3. Fuzzy Matching System

**Library**: Use `rapidfuzz` (faster than fuzzywuzzy, pure Python)

**Matching Strategy**:
```python
class VoiceItemMatcher:
    def __init__(self, inventory_dataset: InventoryDataset):
        self.items = inventory_dataset.items
        # Pre-build search index with variations
        self.search_index = self._build_search_index()

    def _build_search_index(self):
        """Create searchable variations of item names"""
        index = {}
        for item_id, item in self.items.items():
            # Index multiple variations:
            # 1. Full item_id: "WHISKEY Buffalo Trace"
            # 2. Display name: "Buffalo Trace"
            # 3. Category + name: "Whiskey Buffalo"
            # 4. Short forms: "BT", "buff trace", etc.
            variations = self._generate_variations(item)
            index[item_id] = variations
        return index

    def match(self, transcript: str) -> List[MatchResult]:
        """
        Returns top matches with confidence scores

        MatchResult:
            - item_id: str
            - matched_text: str (what part matched)
            - confidence: float (0.0-1.0)
            - method: str ("exact", "fuzzy", "partial")
        """
        # 1. Try exact match first
        # 2. Try fuzzy match with threshold (> 0.85)
        # 3. Try partial ratio for "buffalo" matching "Buffalo Trace"
        # 4. Return top 3 candidates sorted by confidence
```

**Confidence Scoring**:
- **1.0** - Exact match
- **0.85-0.99** - High confidence fuzzy match
- **0.70-0.84** - Medium confidence (requires user verification)
- **< 0.70** - Low confidence (show manual selection UI)

### 4. Voice Input Component

**Technology Options**:

**Option A: Browser Speech Recognition API** (Recommended)
- Built into modern browsers (Chrome, Edge, Safari)
- No backend processing needed
- Real-time transcription
- Implementation: `streamlit-webrtc` or custom Streamlit component

**Option B: Python SpeechRecognition Library**
- Requires audio file upload
- Uses Google Speech API or Whisper (offline)
- More control but slower workflow

**Recommendation**: Use Browser API for live counting, fall back to upload for offline scenarios.

**UI Flow**:
```
[🎤 Start Counting] button
  ↓
[🔴 Listening...] indicator
  ↓
User says: "Buffalo Trace, 3"
  ↓
Transcript appears: "buffalo trace 3"
  ↓
Fuzzy matcher suggests: "WHISKEY Buffalo Trace" (confidence: 0.92)
  ↓
[✓ Confirm] [✏️ Edit] [❌ Skip] buttons
```

### 5. Text Log Editor

**Features**:
- Editable table showing all transcripts
- Columns: Timestamp | Transcript | Matched Item | Count | Confidence | Actions
- Inline editing with `st.data_editor()`
- Re-match button to re-run fuzzy matching after edits
- Bulk verify/delete operations

**Storage**:
- Auto-save after each edit to SQLite
- Keep original `raw_transcript` unchanged
- Store edits in `cleaned_transcript`
- Track `is_verified` flag

### 6. Inventory Sheet Order

**Determine Order From**:
1. **Primary**: Read original BEVWEEKLY Excel sheet row order
2. **Secondary**: Use `inventory_layout.json` location grouping
3. **Tertiary**: Alphabetical by category → vendor → item name

**Implementation**:
```python
def get_inventory_sheet_order(dataset: InventoryDataset) -> List[str]:
    """
    Returns item_ids in the order they appear in inventory sheet

    Sources (priority order):
    1. Original BEVWEEKLY Excel row indices (if available)
    2. inventory_layout.json location groups
    3. Category → Vendor → Name sort
    """
    # Cache this order in VoiceCountSession.inventory_order
```

**User Configuration**:
- Allow user to upload their Excel template to define custom order
- Save preferred order per session

### 7. Excel Export

**Format**:
```
HoundCOGS Voice Count - [Session Name]
Date: [timestamp]

Item Name              | Category  | Vendor    | Location      | Count | System | Variance | Notes
--------------------- | --------- | --------- | ------------- | ----- | ------ | -------- | -----
WHISKEY Buffalo Trace | Whiskey   | Breakthru | top shelf     | 3     | 2.5    | +0.5     | ✓
VODKA Tito's          | Vodka     | Southern  | well 1        | 5     | 6.0    | -1.0     | ✓
...

Unmatched Items:
- "that tequila thing" (Transcript at 14:32)

Summary:
- Items Counted: 47
- Matched: 45 (95.7%)
- Variance: +$23.45
- High Confidence: 42 (89.4%)
```

**Implementation** (`openpyxl`):
```python
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

def export_voice_count_to_excel(session: VoiceCountSession,
                                dataset: InventoryDataset) -> BytesIO:
    """
    Creates Excel workbook with:
    1. Main sheet: Counts in inventory order
    2. Variance sheet: Comparison with system inventory
    3. Log sheet: Full transcript log
    4. Summary sheet: Session statistics
    """
    wb = Workbook()

    # Sheet 1: Count Results (in inventory order)
    ws1 = wb.active
    ws1.title = "Voice Count"
    # ... populate ordered rows

    # Sheet 2: Variance Analysis
    ws2 = wb.create_sheet("Variance")
    # ... compare voice count vs. system

    # Sheet 3: Transcript Log
    ws3 = wb.create_sheet("Transcript Log")
    # ... all records with timestamps

    # Sheet 4: Summary
    ws4 = wb.create_sheet("Summary")
    # ... statistics and metadata

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
```

### 8. UI Integration

**New Tab**: "🎙️ Voice Counting" (add to `zifapp.py` after line 396)

**Layout**:
```
┌─────────────────────────────────────────────────────────┐
│  Voice Counting Session                                 │
│  ┌─────────────────┐  ┌──────────────────┐              │
│  │ New Session     │  │ Load Session ▼  │              │
│  └─────────────────┘  └──────────────────┘              │
├─────────────────────────────────────────────────────────┤
│  Session: "Friday Evening Count"    Status: In Progress │
│  Items Counted: 23  |  High Confidence: 21 (91.3%)     │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────┐       │
│  │  🎤 Start Voice Counting                     │       │
│  │  🔴 Listening... (or) ⏸️ Paused              │       │
│  │                                               │       │
│  │  Last heard: "buffalo trace three"           │       │
│  │  Matched: WHISKEY Buffalo Trace (92%)        │       │
│  │  ✓ Confirm  |  ✏️ Edit  |  ❌ Skip            │       │
│  └──────────────────────────────────────────────┘       │
├─────────────────────────────────────────────────────────┤
│  Transcript Log (Editable)                              │
│  ┌───────────────────────────────────────────────┐      │
│  │ Time  | Transcript       | Matched Item | Cnt │      │
│  │ 14:23 | buffalo trace 3  | WHISKEY Buff | 3 ✓ │      │
│  │ 14:24 | titos five       | VODKA Titos  | 5 ✓ │      │
│  │ 14:25 | that tequila...  | ??? (manual) | - ⚠ │      │
│  └───────────────────────────────────────────────┘      │
│  [Re-match All] [Verify All] [Clear Session]           │
├─────────────────────────────────────────────────────────┤
│  📥 Export to Excel (Inventory Order)                   │
│  📄 Download Transcript (Text)                          │
│  💾 Save Session                                         │
└─────────────────────────────────────────────────────────┘
```

### 9. Session Management

**Features**:
- **Save**: Persist to SQLite at any time
- **Load**: Resume previous sessions from dropdown
- **Delete**: Remove old sessions
- **Auto-save**: Save after each voice input
- **Export History**: Track when sessions were exported

**Storage Functions** (add to `storage.py`):
```python
def save_voice_count_session(session: VoiceCountSession) -> bool
def load_voice_count_session(session_id: str) -> VoiceCountSession
def list_voice_count_sessions() -> List[VoiceCountSession]
def delete_voice_count_session(session_id: str) -> bool
def get_voice_count_records(session_id: str) -> List[VoiceCountRecord]
```

### 10. Variance Analysis Integration

**Compare Voice Count vs. System Inventory**:
```python
def compare_voice_count_to_system(
    session: VoiceCountSession,
    dataset: InventoryDataset,
    week_date: datetime
) -> pd.DataFrame:
    """
    Returns variance report:

    Columns:
    - item_id
    - voice_count
    - system_inventory (from WeeklyRecord)
    - variance (voice - system)
    - variance_pct
    - variance_value (variance * unit_cost)
    - flag (large variance indicator)
    """
```

**Integration with Agent**:
- Agent already has variance analysis logic (`agent.py`)
- Use voice count as "actual count" vs. "system inventory"
- Flag items with >20% variance for investigation

## Implementation Phases

### Phase 1: Data Layer (Foundation)
- Add data models to `models.py`
- Create database schema in `storage.py`
- Add storage functions for CRUD operations

### Phase 2: Fuzzy Matching Engine
- Implement `VoiceItemMatcher` class
- Build search index from inventory
- Test matching accuracy with sample transcripts

### Phase 3: Voice Input UI (MVP)
- Add Voice Counting tab to Streamlit
- Implement text input (manual entry) first
- Add session management (new/save/load)
- Build text log editor

### Phase 4: Speech Recognition
- Add browser speech recognition component
- Integrate with fuzzy matcher
- Add confidence scoring UI

### Phase 5: Excel Export
- Implement inventory order detection
- Build Excel export with openpyxl
- Add variance analysis sheet

### Phase 6: Polish & Testing
- Add unmatched items handling
- Implement bulk operations
- Add summary statistics
- End-to-end testing

## Dependencies to Add

```
# requirements.txt additions
rapidfuzz>=3.0.0          # Fuzzy string matching
openpyxl>=3.1.0           # Excel export (already present)
streamlit-webrtc>=0.47.0  # Browser speech recognition (optional)
```

## Technical Decisions

### Q: How to handle batch products (e.g., "Milagro Marg On Tap")?
**A**: Count the batch item directly. Batch-to-ingredient conversion happens during export/analysis using existing `batch_products.py` logic.

### Q: Should voice counts update WeeklyRecord or stay separate?
**A**: Keep separate initially. Voice counts are point-in-time snapshots for variance detection, not weekly inventory snapshots. Can sync to WeeklyRecord later if needed.

### Q: How to handle mis-hears like "sex on the beach" vs "socks on the beach"?
**A**:
1. Fuzzy matcher will catch phonetic similarities
2. Text log editor lets users correct transcripts
3. Re-match button re-runs fuzzy matching after edits
4. Manual item selection dropdown for ambiguous cases

### Q: What if user's inventory order changes?
**A**:
1. Allow uploading Excel template to define order
2. Save order preference per session
3. Default to last-used order

### Q: Offline support?
**A**:
1. Browser speech API works online only
2. Add fallback: upload audio file → use Whisper for offline transcription
3. SQLite storage is always offline-ready

## Success Metrics

- **Matching Accuracy**: >90% high-confidence matches for typical inventory
- **Speed**: Count 100 items in <10 minutes
- **Export Quality**: Excel format allows direct copy-paste to accounting system
- **Error Recovery**: Easy correction of mis-matched items via text log editor

## Next Steps

1. **Review this plan** - Confirm approach aligns with your workflow
2. **Clarify inventory order** - Provide sample Excel template or describe preferred order
3. **Choose speech input method** - Browser API vs. file upload preference
4. **Start Phase 1** - Begin implementation with data layer

---

**Questions for You:**

1. Do you have a specific Excel template format you use for inventory? Can you share it?
2. Would you prefer live voice input (browser microphone) or upload audio files?
3. What's your typical inventory size? (to optimize fuzzy matching performance)
4. Any specific items that are commonly confused during counting? (to tune matcher)
