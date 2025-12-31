# config/manual_overrides.py
# Manual override mappings for items that need explicit mapping
# These take precedence over all automatic pattern matching

from .constants import COUNT_OZ, STANDARD_POUR_OZ

# Format: "Exact Sales Mix Item Name": {"Inventory Item": oz_per_sale}
# Use the EXACT item name as it appears in your sales mix export
MANUAL_MAPPINGS = {
    "Adios MF": {
        "VODKA Well": 0.5,
        "GIN Well": 0.5,
        "RUM Well": 0.5,
        "TEQUILA Well": 0.5,
        "LIQ Blue Curacao": 0.5,
    },
    "B-52": {
        "LIQ Kahlua": 0.75,
        "LIQ Baileys Irish Cream": 0.75,
        "LIQ Grand Marnier": 0.75,
    },
    "BIG Zipparita": {
        "TEQUILA Well": 2.24,
        "LIQ Triple Sec": 1.504,
    },
    "Bloody Mary": {
        "VODKA Well": 1.5,
        "BAR CONS Bloody Mary": 6.0,
    },
    "Blue Flavor": {
        "LIQ Blue Curacao": 0.375,
    },
    "Blue Flavor 16oz TO GO": {
        "LIQ Blue Curacao": 0.6,
    },
    "Espresso Martini": {
        "blue ice espresso martini": 5.0,
    },
    "Espresso Shot": {
        "blue ice espresso martini": 3.0,
    },
    "Firecracker Flavor": {
        "LIQ Blue Curacao": 0.375,
    },
    "Firecracker Flavor 24oz TO GO": {
        "LIQ Blue Curacao": 0.9,
    },
    "Gimlet Vodka": {
        "VODKA Well": 1.5,
    },
    "Grateful Flavor": {
        "LIQ Blue Curacao": 0.1875,
        "LIQ Chambord": 0.1875,
    },
    "Green Tea": {
        "WHISKEY Jameson": 1.125,
        "LIQ Peach Schnapps": 0.375,
    },
    "Lemon Drop": {
        "VODKA Well": 1.125,
        "LIQ Triple Sec": 0.375,
    },
    "Long Island": {
        "VODKA Well": 0.5,
        "GIN Well": 0.5,
        "RUM Well": 0.5,
        "TEQUILA Well": 0.5,
        "LIQ Triple Sec": 0.5,
    },
    "Margarita": {
        "TEQUILA Well": 1.5,
        "LIQ Triple Sec": 0.375,
    },
    "Martini Up": {
        "VODKA Well": 2.25,
        "LIQ Vermouth Dry": 0.375,
    },
    "Old Fashion": {
        "WHISKEY Well": 1.5,
        "BAR CONS Simple Syrup": 0.25,
        "BAR CONS Bitters": 0.1,
    },
    "TO GO RITA 16oz": {
        "TEQUILA Well": 2.24,
        "LIQ Triple Sec": 1.504,
    },
    "TO GO RITA 24oz": {
        "TEQUILA Well": 3.36,
        "LIQ Triple Sec": 2.256,
    },
    "White Tea": {
        "VODKA Well": 0.75,
        "RUM Malibu Coconut": 0.75,
        "LIQ Chambord": 0.5,
    },
    "Zippa Rona": {
        "Frozen Margarita Batch": 16.0,
        "Coronita": 1.0,
    },
    "Zipparita": {
        "TEQUILA Well": 1.4,
        "LIQ Triple Sec": 0.94,
    },
}

# Set to True to enable manual mappings, False to disable
ENABLE_MANUAL_MAPPINGS = True
