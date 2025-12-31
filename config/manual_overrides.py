# config/manual_overrides.py
# Manual override mappings for items that need explicit mapping
# These take precedence over all automatic pattern matching

from .constants import COUNT_OZ, STANDARD_POUR_OZ

# Format: "Exact Sales Mix Item Name": {"Inventory Item": oz_per_sale}
# Use the EXACT item name as it appears in your sales mix export
MANUAL_MAPPINGS = {
    "[Liquor] Iceberg": {
        "TEQUILA Well": 0.13999999999999999,
        "LIQ Triple Sec": 0.094,
    },
    "[Liquor] Mango Flavor": {
        "BAR CONS Mango Puree": 0.35,
    },
    "[Liquor] Mango Flavor 16oz TO GO": {
        "BAR CONS Mango Puree": 0.65,
    },
    "[Liquor] Mango Flavor 24oz TO GO": {
        "BAR CONS Mango Puree": 0.9,
    },
}

# Set to True to enable manual mappings, False to disable
ENABLE_MANUAL_MAPPINGS = True
