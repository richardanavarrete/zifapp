# Manual Override Mappings Guide

## Overview

Manual overrides allow you to explicitly map sales mix items to inventory usage, bypassing all automatic pattern matching. This is useful for:
- Items that don't match automatically
- Custom drinks with specific recipes
- Quick fixes without modifying pattern matching logic

## How It Works

1. Manual mappings are checked **FIRST** before any automatic matching
2. They use **exact** item name matching (case-sensitive)
3. Once a manual mapping is found, all other matching is skipped
4. Items mapped manually are marked with `[MANUAL]` in the output

## Configuration File

Edit: `config/manual_overrides.py`

## Adding Manual Mappings

### Format

```python
MANUAL_MAPPINGS = {
    "Exact Sales Mix Item Name": {
        "Inventory Item": oz_per_sale,
        "Another Inventory Item": oz_per_sale,
    },
}
```

### Example: Frozen Margarita

```python
MANUAL_MAPPINGS = {
    "[Liquor] Zipparita": {
        "TEQUILA Well": 1.4,        # 10oz × 14% tequila ratio
        "LIQ Triple Sec": 0.94,     # 10oz × 9.4% triple sec ratio
    },
}
```

### Example: Mixed Drink

```python
MANUAL_MAPPINGS = {
    "[Liquor] Bloody Mary": {
        "VODKA Well": 1.5,          # Standard pour
        "BAR CONS Bloody Mary": 6.0,  # Bloody Mary mix
    },
}
```

### Example: Flavored Margarita

```python
MANUAL_MAPPINGS = {
    "[Liquor] Blue Flavor": {
        "TEQUILA Well": 1.4,        # Base tequila
        "LIQ Triple Sec": 0.94,     # Base triple sec
        "LIQ Blue Curacao": 0.375,  # Flavor add
    },
}
```

### Example: Multiple Items

```python
MANUAL_MAPPINGS = {
    "[Liquor] Zipparita": {
        "TEQUILA Well": 1.4,
        "LIQ Triple Sec": 0.94,
    },
    "[Liquor] BIG Zipparita": {
        "TEQUILA Well": 2.24,       # 16oz × 14%
        "LIQ Triple Sec": 1.504,    # 16oz × 9.4%
    },
    "[Liquor] Bloody Mary": {
        "VODKA Well": 1.5,
        "BAR CONS Bloody Mary": 6.0,
    },
}
```

## Finding Exact Item Names

1. Upload your sales mix CSV to the app
2. Look at the "Unmatched Items" section
3. Copy the **exact** item name (including `[Liquor]` prefix)
4. Paste it into `MANUAL_MAPPINGS`

Example from unmatched items:
```
[Liquor] Espresso Martini (qty: 1)
```

Use exactly: `"[Liquor] Espresso Martini"`

## Common Constants

Use these constants from `config/constants.py`:

```python
from .constants import COUNT_OZ, STANDARD_POUR_OZ

# COUNT_OZ = 0.375          # 1-count pour
# STANDARD_POUR_OZ = 1.5    # 4-count pour (standard shot)
```

Example using constants:
```python
MANUAL_MAPPINGS = {
    "[Liquor] Lemon Drop": {
        "VODKA Well": STANDARD_POUR_OZ,  # 1.5oz
        "LIQ Triple Sec": COUNT_OZ,      # 0.375oz
    },
}
```

## Inventory Item Names

Use the exact inventory item names from your system. Common formats:

### Liquor
- `WHISKEY [Brand]` - e.g., `WHISKEY Buffalo Trace`
- `VODKA [Brand]` - e.g., `VODKA Well`
- `TEQUILA [Brand]` - e.g., `TEQUILA Milagro Silver`
- `RUM [Brand]` - e.g., `RUM Bacardi Superior White`
- `GIN [Brand]` - e.g., `GIN Well`

### Liqueurs
- `LIQ [Type]` - e.g., `LIQ Triple Sec`, `LIQ Kahlua`, `LIQ Blue Curacao`

### Beer
- `BEER DFT [Brand]` - e.g., `BEER DFT Bud Light`
- `BEER BTL [Brand]` - e.g., `BEER BTL Modelo`

### Wine
- `WINE [Brand]` - e.g., `WINE Salmon Creek Merlot`

### Bar Consumables
- `BAR CONS [Item]` - e.g., `BAR CONS Bloody Mary`, `BAR CONS Mango Puree`

### Juice/Mixers
- `JUICE [Type]` - e.g., `JUICE Ginger Beer`, `JUICE Red Bull`

## Enabling/Disabling Manual Mappings

In `config/manual_overrides.py`:

```python
# Enable manual mappings
ENABLE_MANUAL_MAPPINGS = True

# Disable manual mappings (use automatic matching only)
ENABLE_MANUAL_MAPPINGS = False
```

## Workflow

1. **Find unmatched items** - Upload sales mix, check unmatched list
2. **Copy exact name** - Copy item name from unmatched list
3. **Add to config** - Edit `config/manual_overrides.py`
4. **Define recipe** - Add inventory items and amounts
5. **Save file** - Changes take effect on next app reload
6. **Re-upload CSV** - Verify item now maps correctly

## Tips

- **Use exact names**: Item names must match exactly (case-sensitive)
- **Check inventory names**: Make sure inventory item names match your system
- **Start simple**: Add one mapping at a time and test
- **Use constants**: Use `COUNT_OZ`, `STANDARD_POUR_OZ` for consistency
- **Mark size variations**: For different sizes, create separate entries
- **Comment your code**: Add comments to explain custom recipes

## Troubleshooting

### Item still shows as unmatched
- Check exact spelling and capitalization
- Verify `ENABLE_MANUAL_MAPPINGS = True`
- Reload the Streamlit app after changes
- Check for trailing spaces in item name

### Item mapping shows wrong amounts
- Verify oz amounts in recipe
- Check if using correct constants
- Ensure inventory item names are correct

### Multiple items mapping to same drink
- Each exact item name needs its own entry
- Example: `"[Liquor] Blue Flavor"` and `"[Liquor] Blue Flavor 16oz TO GO"` are different items

## Example: Full Configuration

```python
# config/manual_overrides.py
from .constants import COUNT_OZ, STANDARD_POUR_OZ

MANUAL_MAPPINGS = {
    # Frozen Margaritas
    "[Liquor] Zipparita": {
        "TEQUILA Well": 1.4,
        "LIQ Triple Sec": 0.94,
    },
    "[Liquor] BIG Zipparita": {
        "TEQUILA Well": 2.24,
        "LIQ Triple Sec": 1.504,
    },

    # Flavored Margaritas
    "[Liquor] Blue Flavor": {
        "TEQUILA Well": 1.4,
        "LIQ Triple Sec": 0.94,
        "LIQ Blue Curacao": COUNT_OZ,
    },
    "[Liquor] Mango Flavor": {
        "TEQUILA Well": 1.4,
        "LIQ Triple Sec": 0.94,
        "BAR CONS Mango Puree": 1.0,
    },

    # Mixed Drinks
    "[Liquor] Bloody Mary": {
        "VODKA Well": STANDARD_POUR_OZ,
        "BAR CONS Bloody Mary": 6.0,
    },
    "[Liquor] Espresso Martini": {
        "VODKA Well": STANDARD_POUR_OZ,
        "LIQ Kahlua": 0.75,
    },
    "[Liquor] Long Island": {
        "VODKA Well": 0.5,
        "GIN Well": 0.5,
        "RUM Well": 0.5,
        "TEQUILA Well": 0.5,
        "LIQ Triple Sec": 0.5,
    },
}

ENABLE_MANUAL_MAPPINGS = false
```
