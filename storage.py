"""
Storage Layer - Persistence for agent memory and run history.

This module provides SQLite-based storage for:
- Agent runs (history of what the agent recommended)
- User actions (what the user actually ordered)
- User preferences (item-specific settings that override defaults)
"""

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

        # Voice count sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS voice_count_sessions (
                session_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                session_name TEXT NOT NULL,
                status TEXT NOT NULL,
                total_items_counted INTEGER DEFAULT 0,
                inventory_order_json TEXT,
                template_file_name TEXT
            )
        """)

        # Voice count records table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS voice_count_records (
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
            )
        """)

        # Create indices for voice count tables
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_voice_records_session
            ON voice_count_records(session_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_voice_records_item
            ON voice_count_records(matched_item_id)
        """)

        conn.commit()


def save_agent_run(
    run_id: str,
    recommendations_df: pd.DataFrame,
    summary: str,
    usage_column: str = 'avg_4wk',
    dataset_hash: Optional[str] = None
):
    """
    Save an agent run and its recommendations.

    Args:
        run_id: Unique identifier for this run
        recommendations_df: DataFrame from recommend_order()
        summary: Summary text describing the run
        usage_column: Which usage average was used
        dataset_hash: Optional hash of the dataset
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Save run summary
        cursor.execute("""
            INSERT INTO agent_runs (
                run_id, timestamp, dataset_hash, usage_column,
                total_items, items_to_order, total_qty_recommended, summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            datetime.now().isoformat(),
            dataset_hash,
            usage_column,
            len(recommendations_df),
            len(recommendations_df[recommendations_df['recommended_qty'] > 0]),
            int(recommendations_df['recommended_qty'].sum()),
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
                float(row['on_hand']),
                float(row['avg_usage']),
                float(row['weeks_on_hand']) if pd.notna(row['weeks_on_hand']) else None,
                float(row['target_weeks']),
                int(row['recommended_qty']),
                json.dumps(row['reason_codes']),
                row['confidence'],
                row['notes']
            ))

        conn.commit()


def save_user_actions(run_id: str, actions: List[Dict]):
    """
    Save user actions (approvals/edits) for a run.

    Args:
        run_id: The run ID these actions are for
        actions: List of dicts with keys:
                 - item_id
                 - recommended_qty
                 - approved_qty
                 - user_override_reason (optional)
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
                action.get('approved_qty', action['recommended_qty']),
                action.get('user_override_reason', ''),
                timestamp
            ))

        conn.commit()


def get_user_prefs() -> Dict[str, Dict]:
    """
    Get all user preferences as a dictionary.

    Returns:
        Dict mapping item_id to preference dict
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_prefs")
        rows = cursor.fetchall()

        prefs = {}
        for row in rows:
            item_id = row[1]  # item_id is column 1
            prefs[item_id] = {
                'target_weeks_override': row[2],
                'never_order': bool(row[3]),
                'preferred_case_rounding': row[4],
                'notes': row[5],
                'last_updated': row[6]
            }
        return prefs


def save_user_pref(item_id: str, **kwargs):
    """
    Save a user preference for an item.

    Args:
        item_id: The item to save preferences for
        **kwargs: Preference fields to update:
                  - target_weeks_override (float)
                  - never_order (bool/int)
                  - preferred_case_rounding (int)
                  - notes (str)
    """
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
                if key in ['target_weeks_override', 'never_order', 'preferred_case_rounding', 'notes']:
                    set_clauses.append(f"{key} = ?")
                    values.append(val)

            if set_clauses:
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
    """
    Get recent agent runs.

    Args:
        limit: Maximum number of runs to return

    Returns:
        DataFrame with run summaries
    """
    with get_db() as conn:
        return pd.read_sql_query(
            "SELECT * FROM agent_runs ORDER BY timestamp DESC LIMIT ?",
            conn,
            params=(limit,)
        )


def get_run_details(run_id: str) -> pd.DataFrame:
    """
    Get detailed recommendations for a specific run.

    Args:
        run_id: The run to get details for

    Returns:
        DataFrame with all recommendations from that run
    """
    with get_db() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM agent_recs WHERE run_id = ? ORDER BY item_id",
            conn,
            params=(run_id,)
        )
        if not df.empty:
            # Parse reason_codes back from JSON
            df['reason_codes'] = df['reason_codes'].apply(json.loads)
        return df


def get_run_actions(run_id: str) -> pd.DataFrame:
    """
    Get user actions for a specific run.

    Args:
        run_id: The run to get actions for

    Returns:
        DataFrame with user actions
    """
    with get_db() as conn:
        return pd.read_sql_query(
            "SELECT * FROM agent_actions WHERE run_id = ? ORDER BY timestamp",
            conn,
            params=(run_id,)
        )


def get_item_history(item_id: str, limit: int = 10) -> Dict:
    """
    Get recommendation and action history for a specific item.

    Args:
        item_id: The item to get history for
        limit: Maximum number of runs to look back

    Returns:
        Dictionary with recommendations and actions history
    """
    with get_db() as conn:
        # Get recent recommendations for this item
        recs_df = pd.read_sql_query("""
            SELECT r.*, ar.timestamp, ar.summary
            FROM agent_recs r
            JOIN agent_runs ar ON r.run_id = ar.run_id
            WHERE r.item_id = ?
            ORDER BY ar.timestamp DESC
            LIMIT ?
        """, conn, params=(item_id, limit))

        # Get recent actions for this item
        actions_df = pd.read_sql_query("""
            SELECT * FROM agent_actions
            WHERE item_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, conn, params=(item_id, limit))

        return {
            'recommendations': recs_df,
            'actions': actions_df
        }


# ============================================================================
# Voice Count Session Management
# ============================================================================

def save_voice_count_session(session) -> bool:
    """
    Save or update a voice count session.

    Args:
        session: VoiceCountSession object

    Returns:
        True if successful
    """
    from models import VoiceCountSession  # Import here to avoid circular dependency

    with get_db() as conn:
        cursor = conn.cursor()

        # Check if session exists
        cursor.execute("SELECT session_id FROM voice_count_sessions WHERE session_id = ?", (session.session_id,))
        existing = cursor.fetchone()

        inventory_order_json = json.dumps(session.inventory_order) if session.inventory_order else None

        if existing:
            # Update existing session
            cursor.execute("""
                UPDATE voice_count_sessions
                SET updated_at = ?, session_name = ?, status = ?,
                    total_items_counted = ?, inventory_order_json = ?, template_file_name = ?
                WHERE session_id = ?
            """, (
                session.updated_at.isoformat(),
                session.session_name,
                session.status,
                session.total_items_counted,
                inventory_order_json,
                session.template_file_name,
                session.session_id
            ))
        else:
            # Insert new session
            cursor.execute("""
                INSERT INTO voice_count_sessions (
                    session_id, created_at, updated_at, session_name,
                    status, total_items_counted, inventory_order_json, template_file_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session.session_id,
                session.created_at.isoformat(),
                session.updated_at.isoformat(),
                session.session_name,
                session.status,
                session.total_items_counted,
                inventory_order_json,
                session.template_file_name
            ))

        # Save all records for this session
        # First delete existing records to avoid duplicates
        cursor.execute("DELETE FROM voice_count_records WHERE session_id = ?", (session.session_id,))

        # Then insert all current records
        for record in session.records:
            cursor.execute("""
                INSERT INTO voice_count_records (
                    record_id, session_id, timestamp, raw_transcript,
                    cleaned_transcript, matched_item_id, count_value,
                    confidence_score, match_method, is_verified, location, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.record_id,
                record.session_id,
                record.timestamp.isoformat(),
                record.raw_transcript,
                record.cleaned_transcript,
                record.matched_item_id,
                record.count_value,
                record.confidence_score,
                record.match_method,
                1 if record.is_verified else 0,
                record.location,
                record.notes
            ))

        conn.commit()
        return True


def load_voice_count_session(session_id: str):
    """
    Load a voice count session from the database.

    Args:
        session_id: The session ID to load

    Returns:
        VoiceCountSession object or None if not found
    """
    from models import VoiceCountSession, VoiceCountRecord  # Import here to avoid circular dependency

    with get_db() as conn:
        cursor = conn.cursor()

        # Load session
        cursor.execute("SELECT * FROM voice_count_sessions WHERE session_id = ?", (session_id,))
        session_row = cursor.fetchone()

        if not session_row:
            return None

        # Parse inventory order
        inventory_order = json.loads(session_row[6]) if session_row[6] else []

        # Load records
        cursor.execute("SELECT * FROM voice_count_records WHERE session_id = ? ORDER BY timestamp", (session_id,))
        record_rows = cursor.fetchall()

        records = []
        for row in record_rows:
            records.append(VoiceCountRecord(
                record_id=row[0],
                session_id=row[1],
                timestamp=datetime.fromisoformat(row[2]),
                raw_transcript=row[3],
                cleaned_transcript=row[4],
                matched_item_id=row[5],
                count_value=row[6],
                confidence_score=row[7],
                match_method=row[8],
                is_verified=bool(row[9]),
                location=row[10],
                notes=row[11]
            ))

        return VoiceCountSession(
            session_id=session_row[0],
            created_at=datetime.fromisoformat(session_row[1]),
            updated_at=datetime.fromisoformat(session_row[2]),
            session_name=session_row[3],
            status=session_row[4],
            total_items_counted=session_row[5],
            records=records,
            inventory_order=inventory_order,
            template_file_name=session_row[7]
        )


def list_voice_count_sessions(limit: int = 50) -> List[Dict]:
    """
    List all voice count sessions.

    Args:
        limit: Maximum number of sessions to return

    Returns:
        List of session summary dicts
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT session_id, created_at, updated_at, session_name, status, total_items_counted
            FROM voice_count_sessions
            ORDER BY updated_at DESC
            LIMIT ?
        """, (limit,))

        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                'session_id': row[0],
                'created_at': row[1],
                'updated_at': row[2],
                'session_name': row[3],
                'status': row[4],
                'total_items_counted': row[5]
            })

        return sessions


def delete_voice_count_session(session_id: str) -> bool:
    """
    Delete a voice count session and all its records.

    Args:
        session_id: The session to delete

    Returns:
        True if successful
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Delete records first (foreign key constraint)
        cursor.execute("DELETE FROM voice_count_records WHERE session_id = ?", (session_id,))

        # Delete session
        cursor.execute("DELETE FROM voice_count_sessions WHERE session_id = ?", (session_id,))

        conn.commit()
        return True


def get_voice_count_records(session_id: str) -> List[Dict]:
    """
    Get all records for a specific voice count session.

    Args:
        session_id: The session ID

    Returns:
        List of record dicts
    """
    with get_db() as conn:
        return pd.read_sql_query(
            "SELECT * FROM voice_count_records WHERE session_id = ? ORDER BY timestamp",
            conn,
            params=(session_id,)
        ).to_dict('records')
