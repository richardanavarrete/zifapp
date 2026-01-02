# Fix for Iceberg and Other Unmapped Items

## The Problem

When you see `[Liquor] Iceberg` in the unmapped items list, the category prefix `[Liquor]` is just for display. The actual item name in the sales data is just `"Iceberg"`.

## The Solution

Use the item name **WITHOUT** the category prefix in your mappings:

### ❌ Wrong (won't work):
```python
MANUAL_MAPPINGS = {
    "[Liquor] Iceberg": {  # This WON'T match!
        "TEQUILA Well": 0.14,
        "LIQ Triple Sec": 0.094,
    },
}
```

### ✅ Correct (will work):
```python
MANUAL_MAPPINGS = {
    "Iceberg": {  # This WILL match!
        "TEQUILA Well": 0.14,
        "LIQ Triple Sec": 0.094,
    },
}
```

## Quick Reference

When you see these in the unmapped list, use these mapping keys:

| Unmapped Display | Mapping Key to Use |
|-----------------|-------------------|
| `[Liquor] Iceberg` | `"Iceberg"` |
| `[Liquor] Green Tea` | `"Green Tea"` |
| `[Liquor] Adios MF` | `"Adios MF"` |
| `[Draft] Some Beer` | `"Some Beer"` |
| `[Wine] Some Wine` | `"Some Wine"` |

## Why This Happens

The sales mix CSV has separate columns:
- **Category**: "Liquor" (separate column)
- **Item**: "Iceberg" (separate column)

The unmatched list combines them as `[Category] Item` for display, but the actual lookup uses just the Item name.

## Your Current Fix

I've already updated your config file to use `"Iceberg"` instead of `"[Liquor] Iceberg"`.

**Refresh your browser** at http://localhost:8502 and Iceberg should now show as mapped!
