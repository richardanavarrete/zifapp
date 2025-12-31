"""
Database module for ZifApp - Handles all SQLite database operations
"""
import sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path
import hashlib
import json

DB_PATH = Path("zifapp_data.db")


def get_connection():
    """Get a database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn


def init_database():
    """Initialize the database with all required tables"""
    conn = get_connection()
    cursor = conn.cursor()

    # Table 1: Weekly Usage History
    # Stores one record per item per week (no duplicates)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS weekly_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            week_ending DATE NOT NULL,
            usage REAL NOT NULL,
            end_inventory REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(item_name, week_ending)
        )
    """)

    # Table 2: Sales Mix Data
    # Stores parsed sales mix data from GEMpos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales_mix (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_ending DATE NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT,
            item TEXT NOT NULL,
            qty INTEGER NOT NULL,
            amount REAL NOT NULL,
            data_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(week_ending, category, item, data_hash)
        )
    """)

    # Table 3: Daily Sales Totals
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_date DATE NOT NULL UNIQUE,
            total_sales REAL NOT NULL,
            guest_count INTEGER,
            avg_check REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table 4: Events and Games
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_date DATE NOT NULL,
            event_type TEXT NOT NULL,  -- 'game', 'holiday', 'special', etc.
            event_name TEXT NOT NULL,
            home_team TEXT,
            away_team TEXT,
            game_time TIME,
            expected_impact TEXT,  -- 'high', 'medium', 'low'
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table 5: Weather Data
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS weather (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            weather_date DATE NOT NULL UNIQUE,
            high_temp REAL,
            low_temp REAL,
            avg_temp REAL,
            precipitation REAL,  -- inches
            conditions TEXT,  -- 'sunny', 'rainy', 'cloudy', etc.
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table 6: Hourly Sales Patterns
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hourly_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_date DATE NOT NULL,
            hour INTEGER NOT NULL,  -- 0-23
            sales REAL NOT NULL,
            guest_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(sale_date, hour)
        )
    """)

    # Table 7: Category Sales Breakdown
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS category_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_date DATE NOT NULL,
            category TEXT NOT NULL,
            sales REAL NOT NULL,
            qty INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(sale_date, category)
        )
    """)

    # Table 8: Manual Mappings History
    # Track when mappings were added/changed
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mapping_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            mapping_json TEXT NOT NULL,  -- JSON of the mapping recipe
            action TEXT NOT NULL,  -- 'created', 'updated', 'deleted'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes for common queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_week ON weekly_usage(week_ending)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_item ON weekly_usage(item_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON daily_sales(sale_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_date ON events(event_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_weather_date ON weather(weather_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_hourly_date ON hourly_sales(sale_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_category_date ON category_sales(sale_date)")

    conn.commit()
    conn.close()


def save_weekly_usage(usage_df: pd.DataFrame, week_ending: str):
    """
    Save weekly usage data (one record per item per week)
    Uses INSERT OR REPLACE to avoid duplicates

    Args:
        usage_df: DataFrame with columns ['Item', 'Usage', 'End Inventory']
        week_ending: Date string for the week ending (e.g., '2024-01-07')
    """
    conn = get_connection()
    cursor = conn.cursor()

    week_date = pd.to_datetime(week_ending).date()

    for _, row in usage_df.iterrows():
        cursor.execute("""
            INSERT OR REPLACE INTO weekly_usage
            (item_name, week_ending, usage, end_inventory)
            VALUES (?, ?, ?, ?)
        """, (
            str(row['Item']),
            week_date,
            float(row['Usage']),
            float(row['End Inventory'])
        ))

    conn.commit()
    conn.close()

    return cursor.rowcount


def save_sales_mix(sales_df: pd.DataFrame, week_ending: str):
    """
    Save sales mix data with duplicate detection via hash

    Args:
        sales_df: DataFrame with columns ['Category', 'Subcategory', 'Item', 'Qty', 'Amount']
        week_ending: Date string for the week ending
    """
    conn = get_connection()
    cursor = conn.cursor()

    week_date = pd.to_datetime(week_ending).date()
    inserted = 0

    for _, row in sales_df.iterrows():
        # Create hash of the data to detect duplicates
        data_str = f"{row['Category']}|{row['Item']}|{row['Qty']}|{row['Amount']}"
        data_hash = hashlib.md5(data_str.encode()).hexdigest()

        try:
            cursor.execute("""
                INSERT INTO sales_mix
                (week_ending, category, subcategory, item, qty, amount, data_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                week_date,
                str(row['Category']),
                str(row.get('Subcategory', '')),
                str(row['Item']),
                int(row['Qty']),
                float(row['Amount']),
                data_hash
            ))
            inserted += 1
        except sqlite3.IntegrityError:
            # Duplicate detected, skip
            pass

    conn.commit()
    conn.close()

    return inserted


def get_usage_history(item_name: str = None, weeks: int = None):
    """
    Get usage history for forecasting

    Args:
        item_name: Optional item name to filter
        weeks: Optional number of recent weeks to return

    Returns:
        DataFrame with usage history
    """
    conn = get_connection()

    query = "SELECT * FROM weekly_usage"
    conditions = []
    params = []

    if item_name:
        conditions.append("item_name = ?")
        params.append(item_name)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY week_ending DESC"

    if weeks:
        query += f" LIMIT {weeks}"

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    return df


def save_event(event_date: str, event_type: str, event_name: str, **kwargs):
    """
    Save an event (game, holiday, etc.)

    Args:
        event_date: Date of the event
        event_type: Type of event ('game', 'holiday', 'special')
        event_name: Name of the event
        **kwargs: Additional fields (home_team, away_team, game_time, expected_impact, notes)
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO events
        (event_date, event_type, event_name, home_team, away_team, game_time, expected_impact, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        pd.to_datetime(event_date).date(),
        event_type,
        event_name,
        kwargs.get('home_team'),
        kwargs.get('away_team'),
        kwargs.get('game_time'),
        kwargs.get('expected_impact'),
        kwargs.get('notes')
    ))

    conn.commit()
    event_id = cursor.lastrowid
    conn.close()

    return event_id


def save_hourly_sales(hourly_df: pd.DataFrame, sale_date: str):
    """
    Save hourly sales pattern for labor forecasting

    Args:
        hourly_df: DataFrame with columns ['hour', 'sales', 'guest_count']
        sale_date: Date string
    """
    conn = get_connection()
    cursor = conn.cursor()

    date = pd.to_datetime(sale_date).date()

    for _, row in hourly_df.iterrows():
        cursor.execute("""
            INSERT OR REPLACE INTO hourly_sales
            (sale_date, hour, sales, guest_count)
            VALUES (?, ?, ?, ?)
        """, (
            date,
            int(row['hour']),
            float(row['sales']),
            int(row.get('guest_count', 0))
        ))

    conn.commit()
    conn.close()

    return cursor.rowcount


def save_category_sales(category_df: pd.DataFrame, sale_date: str):
    """
    Save category sales breakdown

    Args:
        category_df: DataFrame with columns ['category', 'sales', 'qty']
        sale_date: Date string
    """
    conn = get_connection()
    cursor = conn.cursor()

    date = pd.to_datetime(sale_date).date()

    for _, row in category_df.iterrows():
        cursor.execute("""
            INSERT OR REPLACE INTO category_sales
            (sale_date, category, sales, qty)
            VALUES (?, ?, ?, ?)
        """, (
            date,
            str(row['category']),
            float(row['sales']),
            int(row.get('qty', 0))
        ))

    conn.commit()
    conn.close()

    return cursor.rowcount


def log_mapping_change(item_name: str, mapping_dict: dict, action: str):
    """
    Log when manual mappings are created/updated/deleted

    Args:
        item_name: The item being mapped
        mapping_dict: The mapping recipe (dict of inv_item: oz)
        action: 'created', 'updated', or 'deleted'
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO mapping_history
        (item_name, mapping_json, action)
        VALUES (?, ?, ?)
    """, (
        item_name,
        json.dumps(mapping_dict),
        action
    ))

    conn.commit()
    conn.close()

    return cursor.lastrowid


def get_stats():
    """Get database statistics"""
    conn = get_connection()
    cursor = conn.cursor()

    stats = {}

    # Count records in each table
    tables = [
        'weekly_usage', 'sales_mix', 'daily_sales', 'events',
        'weather', 'hourly_sales', 'category_sales', 'mapping_history'
    ]

    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        stats[table] = cursor.fetchone()[0]

    # Get date ranges
    cursor.execute("SELECT MIN(week_ending), MAX(week_ending) FROM weekly_usage")
    usage_range = cursor.fetchone()
    stats['usage_date_range'] = usage_range if usage_range[0] else (None, None)

    cursor.execute("SELECT MIN(sale_date), MAX(sale_date) FROM daily_sales")
    sales_range = cursor.fetchone()
    stats['sales_date_range'] = sales_range if sales_range[0] else (None, None)

    conn.close()

    return stats


# Initialize database on import
init_database()
