"""
SQLite Repository

Handles all database operations using SQLite.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from houndcogs.models.inventory import DatasetSummary, InventoryDataset, Item, WeeklyRecord
from houndcogs.models.orders import AgentRun, OrderConstraints, OrderTargets

logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DB_PATH = "./data/db/houndcogs.db"


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get a database connection."""
    db_path = db_path or os.environ.get("DATABASE_PATH", DEFAULT_DB_PATH)

    # Ensure directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_database(db_path: Optional[str] = None):
    """Initialize database tables."""
    conn = get_connection(db_path)

    try:
        cursor = conn.cursor()

        # Datasets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS datasets (
                dataset_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                source_files TEXT,
                date_range_start TEXT,
                date_range_end TEXT,
                items_count INTEGER DEFAULT 0,
                weeks_count INTEGER DEFAULT 0,
                metadata TEXT
            )
        """)

        # Items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS items (
                item_id TEXT,
                dataset_id TEXT,
                display_name TEXT,
                category TEXT,
                vendor TEXT,
                location TEXT,
                unit_cost REAL DEFAULT 0,
                unit_of_measure TEXT DEFAULT 'bottle',
                metadata TEXT,
                PRIMARY KEY (item_id, dataset_id),
                FOREIGN KEY (dataset_id) REFERENCES datasets(dataset_id)
            )
        """)

        # Weekly records table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS weekly_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id TEXT NOT NULL,
                dataset_id TEXT NOT NULL,
                week_date TEXT NOT NULL,
                on_hand REAL NOT NULL,
                usage REAL NOT NULL,
                week_name TEXT,
                source_file TEXT,
                FOREIGN KEY (dataset_id) REFERENCES datasets(dataset_id)
            )
        """)

        # Agent runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_runs (
                run_id TEXT PRIMARY KEY,
                dataset_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                targets TEXT,
                constraints TEXT,
                summary TEXT,
                status TEXT DEFAULT 'completed',
                FOREIGN KEY (dataset_id) REFERENCES datasets(dataset_id)
            )
        """)

        # Agent recommendations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                suggested_order INTEGER,
                reason_code TEXT,
                confidence TEXT,
                data TEXT,
                FOREIGN KEY (run_id) REFERENCES agent_runs(run_id)
            )
        """)

        # Voice sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS voice_sessions (
                session_id TEXT PRIMARY KEY,
                session_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT DEFAULT 'in_progress',
                location TEXT,
                notes TEXT,
                metadata TEXT
            )
        """)

        # Voice count records table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS voice_count_records (
                record_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                item_id TEXT,
                display_name TEXT,
                match_confidence REAL DEFAULT 0,
                quantity REAL NOT NULL,
                unit TEXT DEFAULT 'bottles',
                confirmed INTEGER DEFAULT 0,
                rejected INTEGER DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES voice_sessions(session_id)
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_dataset ON weekly_records(dataset_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_item ON weekly_records(item_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_recs_run ON agent_recommendations(run_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_voice_session ON voice_count_records(session_id)")

        conn.commit()
        logger.info("Database initialized successfully")

    finally:
        conn.close()


# Dataset operations

def save_dataset(dataset: InventoryDataset, db_path: Optional[str] = None):
    """Save an inventory dataset to the database."""
    conn = get_connection(db_path)

    try:
        cursor = conn.cursor()

        # Insert dataset
        cursor.execute("""
            INSERT OR REPLACE INTO datasets
            (dataset_id, name, created_at, source_files, date_range_start, date_range_end, items_count, weeks_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dataset.dataset_id,
            dataset.name,
            dataset.created_at.isoformat(),
            json.dumps(dataset.source_files),
            dataset.date_range_start.isoformat() if dataset.date_range_start else None,
            dataset.date_range_end.isoformat() if dataset.date_range_end else None,
            dataset.items_count,
            dataset.weeks_count,
        ))

        # Insert items
        for item_id, item in dataset.items.items():
            cursor.execute("""
                INSERT OR REPLACE INTO items
                (item_id, dataset_id, display_name, category, vendor, location, unit_cost, unit_of_measure)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item_id,
                dataset.dataset_id,
                item.display_name,
                item.category.value if hasattr(item.category, 'value') else str(item.category),
                item.vendor.value if hasattr(item.vendor, 'value') else str(item.vendor),
                item.location,
                item.unit_cost,
                item.unit_of_measure,
            ))

        # Insert records
        for record in dataset.records:
            cursor.execute("""
                INSERT INTO weekly_records
                (item_id, dataset_id, week_date, on_hand, usage, week_name, source_file)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                record.item_id,
                dataset.dataset_id,
                record.week_date.isoformat(),
                record.on_hand,
                record.usage,
                record.week_name,
                record.source_file,
            ))

        conn.commit()
        logger.info(f"Saved dataset {dataset.dataset_id}")

    finally:
        conn.close()


def get_dataset(dataset_id: str, db_path: Optional[str] = None) -> Optional[InventoryDataset]:
    """Load a dataset from the database."""
    conn = get_connection(db_path)

    try:
        cursor = conn.cursor()

        # Get dataset metadata
        cursor.execute("SELECT * FROM datasets WHERE dataset_id = ?", (dataset_id,))
        row = cursor.fetchone()

        if not row:
            return None

        # Get items
        cursor.execute("SELECT * FROM items WHERE dataset_id = ?", (dataset_id,))
        items = {}
        for item_row in cursor.fetchall():
            items[item_row['item_id']] = Item(
                item_id=item_row['item_id'],
                display_name=item_row['display_name'],
                category=item_row['category'],
                vendor=item_row['vendor'],
                location=item_row['location'],
                unit_cost=item_row['unit_cost'],
                unit_of_measure=item_row['unit_of_measure'],
            )

        # Get records
        cursor.execute("SELECT * FROM weekly_records WHERE dataset_id = ?", (dataset_id,))
        records = []
        for rec_row in cursor.fetchall():
            records.append(WeeklyRecord(
                item_id=rec_row['item_id'],
                week_date=rec_row['week_date'],
                on_hand=rec_row['on_hand'],
                usage=rec_row['usage'],
                week_name=rec_row['week_name'],
                source_file=rec_row['source_file'],
            ))

        return InventoryDataset(
            dataset_id=row['dataset_id'],
            name=row['name'],
            created_at=datetime.fromisoformat(row['created_at']),
            source_files=json.loads(row['source_files']) if row['source_files'] else [],
            date_range_start=row['date_range_start'],
            date_range_end=row['date_range_end'],
            items_count=row['items_count'],
            weeks_count=row['weeks_count'],
            items=items,
            records=records,
        )

    finally:
        conn.close()


def list_datasets(
    page: int = 1,
    page_size: int = 50,
    db_path: Optional[str] = None
) -> List[DatasetSummary]:
    """List all datasets."""
    conn = get_connection(db_path)

    try:
        cursor = conn.cursor()
        offset = (page - 1) * page_size

        cursor.execute("""
            SELECT * FROM datasets
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (page_size, offset))

        results = []
        for row in cursor.fetchall():
            results.append(DatasetSummary(
                dataset_id=row['dataset_id'],
                name=row['name'],
                created_at=datetime.fromisoformat(row['created_at']),
                items_count=row['items_count'],
                weeks_count=row['weeks_count'],
                date_range_start=row['date_range_start'],
                date_range_end=row['date_range_end'],
                source_files=json.loads(row['source_files']) if row['source_files'] else [],
            ))

        return results

    finally:
        conn.close()


# Agent run operations

def save_agent_run(run: AgentRun, db_path: Optional[str] = None):
    """Save an agent run to the database."""
    conn = get_connection(db_path)

    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO agent_runs
            (run_id, dataset_id, created_at, targets, constraints, summary, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            run.run_id,
            run.dataset_id,
            run.created_at.isoformat(),
            run.targets.model_dump_json(),
            run.constraints.model_dump_json(),
            run.summary.model_dump_json(),
            run.status,
        ))

        # Save recommendations
        for rec in run.recommendations:
            cursor.execute("""
                INSERT INTO agent_recommendations
                (run_id, item_id, suggested_order, reason_code, confidence, data)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                run.run_id,
                rec.item_id,
                rec.suggested_order,
                rec.reason_code.value if hasattr(rec.reason_code, 'value') else str(rec.reason_code),
                rec.confidence.value if hasattr(rec.confidence, 'value') else str(rec.confidence),
                rec.model_dump_json(),
            ))

        conn.commit()
        logger.info(f"Saved agent run {run.run_id}")

    finally:
        conn.close()


def get_agent_run(run_id: str, db_path: Optional[str] = None) -> Optional[AgentRun]:
    """Load an agent run from the database."""
    conn = get_connection(db_path)

    try:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM agent_runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()

        if not row:
            return None

        # Load recommendations
        cursor.execute(
            "SELECT data FROM agent_recommendations WHERE run_id = ?",
            (run_id,)
        )
        recommendations = []
        for rec_row in cursor.fetchall():
            from houndcogs.models.orders import Recommendation
            recommendations.append(Recommendation.model_validate_json(rec_row['data']))

        from houndcogs.models.orders import AgentRunSummary

        return AgentRun(
            run_id=row['run_id'],
            dataset_id=row['dataset_id'],
            created_at=datetime.fromisoformat(row['created_at']),
            targets=OrderTargets.model_validate_json(row['targets']),
            constraints=OrderConstraints.model_validate_json(row['constraints']),
            summary=AgentRunSummary.model_validate_json(row['summary']),
            recommendations=recommendations,
            status=row['status'],
        )

    finally:
        conn.close()
