# Database Guide for ZifApp

## Overview

ZifApp now includes a SQLite database (`zifapp_data.db`) that automatically stores historical data for sales and labor forecasting. The database is designed to eliminate duplicates and maintain clean, analyzable data.

## What Gets Stored Automatically

### 1. Weekly Usage Data
- **When**: Every time you upload a BEVWEEKLY Excel file
- **What**: One record per item per week (no duplicates)
- **Columns**: item_name, week_ending, usage, end_inventory
- **Deduplication**: Uses `UNIQUE(item_name, week_ending)` constraint

### 2. Sales Mix Data
- **When**: Every time you upload a Sales Mix CSV
- **What**: Parsed sales data from GEMpos
- **Columns**: week_ending, category, subcategory, item, qty, amount, data_hash
- **Deduplication**: Uses hash-based duplicate detection

### 3. Manual Mapping Changes
- **When**: Every time you create, update, or delete a manual mapping
- **What**: Complete history of all mapping changes
- **Columns**: item_name, mapping_json, action, created_at

## Database Schema

### Tables Ready for Use

1. **weekly_usage** - Inventory usage history
2. **sales_mix** - Detailed sales transactions
3. **daily_sales** - Daily sales totals (ready for your data)
4. **events** - Games, holidays, special events (ready for your data)
5. **weather** - Weather data for correlation analysis (ready for your data)
6. **hourly_sales** - Hourly sales patterns for labor scheduling (ready for your data)
7. **category_sales** - Sales breakdown by category (ready for your data)
8. **mapping_history** - Audit trail of mapping changes

## Using the Database Tab

Navigate to the **💾 Database** tab to:

1. **View Statistics**: See how many records are stored in each table
2. **Check Data Coverage**: See date ranges for your stored data
3. **Search Usage History**: Look up any item and see its usage trend
4. **View Charts**: Visualize usage patterns over time
5. **Track Mapping Changes**: See when mappings were created/modified

## Future Forecasting Features

The database is structured to support these future features:

### Sales Forecasting
```python
# Example: Get 10 weeks of usage history for forecasting
history_df = db.get_usage_history(item_name="VODKA Well", weeks=10)
# Use this data with your forecasting model
```

### Event Impact Analysis
```python
# Add events that might impact sales
db.save_event(
    event_date="2025-02-02",
    event_type="game",
    event_name="Super Bowl",
    expected_impact="high"
)
```

### Hourly Sales Patterns (for Labor Scheduling)
```python
# Add hourly sales data
hourly_df = pd.DataFrame({
    'hour': range(11, 23),  # 11am-11pm
    'sales': [120, 150, 200, ...],
    'guest_count': [15, 20, 30, ...]
})
db.save_hourly_sales(hourly_df, sale_date="2025-01-15")
```

### Weather Correlation
```python
# Track weather to correlate with sales
db.save_weather(
    weather_date="2025-01-15",
    high_temp=75,
    conditions="sunny",
    precipitation=0
)
```

## API Reference

### Reading Data

```python
import database as db

# Get usage history
history = db.get_usage_history(
    item_name="VODKA Well",  # Optional
    weeks=10  # Optional
)

# Get database statistics
stats = db.get_stats()

# Custom queries
conn = db.get_connection()
df = pd.read_sql_query("SELECT * FROM weekly_usage WHERE item_name = ?", conn, params=["VODKA Well"])
conn.close()
```

### Writing Data (for future features)

```python
# Save daily sales
db.save_daily_sales(date, total_sales, guest_count, avg_check)

# Save event
db.save_event(
    event_date="2025-01-15",
    event_type="game",
    event_name="Wildcats vs Suns",
    home_team="Wildcats",
    expected_impact="medium"
)

# Save weather
db.save_weather(weather_date, high_temp, low_temp, conditions)

# Save hourly pattern
db.save_hourly_sales(hourly_df, sale_date)

# Save category breakdown
db.save_category_sales(category_df, sale_date)
```

## Data Export

You can export data from the database tab or directly:

```python
import sqlite3
import pandas as pd

conn = sqlite3.connect('zifapp_data.db')
df = pd.read_sql_query("SELECT * FROM weekly_usage", conn)
df.to_csv('usage_history.csv', index=False)
conn.close()
```

## Best Practices

1. **Upload data regularly**: Upload BEVWEEKLY and Sales Mix files each week to build history
2. **Check the Database tab**: Monitor that data is being saved correctly
3. **No manual cleanup needed**: Duplicate prevention is automatic
4. **Track events**: Add significant events (games, holidays) to improve forecasting
5. **Monitor storage**: SQLite databases are self-contained and efficient

## Backup

The database file is at: `zifapp_data.db`

To backup:
```bash
# Simple copy
cp zifapp_data.db zifapp_data_backup_2025-01-15.db

# Or use SQLite backup
sqlite3 zifapp_data.db ".backup zifapp_backup.db"
```

## Troubleshooting

**"No usage history found"**
- Make sure you've uploaded BEVWEEKLY files
- Check that the item name matches exactly (case-sensitive)

**"Database save warning"**
- Usually means a duplicate was detected (this is normal)
- Check the Database tab to verify data was saved

**Database file missing**
- The database auto-creates on first run
- If deleted, it will recreate empty on next app start

## Next Steps

Ready to implement forecasting? Consider:
1. Collecting 4+ weeks of data first
2. Adding event data for your busiest periods
3. Implementing time-series forecasting models (ARIMA, Prophet, etc.)
4. Building labor scheduling based on hourly patterns
