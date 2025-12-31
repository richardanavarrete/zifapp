# config/manual_overrides.py
# Manual override mappings for items that need explicit mapping
# These take precedence over all automatic pattern matching

from .constants import COUNT_OZ, STANDARD_POUR_OZ

# Format: "Exact Sales Mix Item Name": {"Inventory Item": oz_per_sale}
# Use the EXACT item name as it appears in your sales mix export
MANUAL_MAPPINGS = {
    # Example frozen margaritas
    # "[Liquor] Zipparita": {
    #     "TEQUILA Well": 1.4,  # 10oz marg * 14% tequila ratio
    #     "LIQ Triple Sec": 0.94,  # 10oz marg * 9.4% triple sec ratio
    # },

    # Example mixed drink
    # "[Liquor] Bloody Mary": {
    #     "VODKA Well": STANDARD_POUR_OZ,
    #     "BAR CONS Bloody Mary": 6.0,
    # },

    # Add your manual mappings here:

}

# Set to True to enable manual mappings, False to disable
ENABLE_MANUAL_MAPPINGS = True
