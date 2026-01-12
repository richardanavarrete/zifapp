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
