# config/manual_overrides.py
# Manual override mappings for items that need explicit mapping
# These take precedence over all automatic pattern matching

from .constants import COUNT_OZ, STANDARD_POUR_OZ

# Format: "Exact Sales Mix Item Name": {"Inventory Item": oz_per_sale}
# Use the EXACT item name as it appears in your sales mix export
MANUAL_MAPPINGS = {
    "[Liquor] Adios MF": {
        "VODKA Well": 0.5,
        "GIN Well": 0.5,
        "RUM Well": 0.5,
        "TEQUILA Well": 0.5,
        "LIQ Blue Curacao": 0.5,
    },
    "[Liquor] Margarita": {
        "TEQUILA Well": 1.5,
        "LIQ Triple Sec": 0.375,
    },
    "[Liquor] TO GO RITA 16oz": {
        "TEQUILA Well": 2.24,
        "LIQ Triple Sec": 1.504,
    },
    "[Liquor] TO GO RITA 24oz": {
        "TEQUILA Well": 3.36,
        "LIQ Triple Sec": 2.256,
    },
    "[Liquor] Zippa Rona": {
        "Frozen Margarita Batch": 16.0,
        "Coronita": 1.0,
    },
    "[Liquor] Zipparita": {
        "TEQUILA Well": 1.4,
        "LIQ Triple Sec": 0.94,
    },
}

# Set to True to enable manual mappings, False to disable
ENABLE_MANUAL_MAPPINGS = True
