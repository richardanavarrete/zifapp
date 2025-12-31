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
    "[Liquor] B-52": {
        "LIQ Kahlua": 0.75,
        "LIQ Baileys Irish Cream": 0.75,
        "LIQ Grand Marnier": 0.75,
    },
    "[Liquor] BIG Zipparita": {
        "TEQUILA Well": 2.24,
        "LIQ Triple Sec": 1.504,
    },
    "[Liquor] Bloody Mary": {
        "VODKA Well": 1.5,
        "BAR CONS Bloody Mary": 6.0,
    },
    "[Liquor] Blue Flavor": {
        "LIQ Blue Curacao": 0.375,
    },
    "[Liquor] Blue Flavor 16oz TO GO": {
        "LIQ Blue Curacao": 0.6000000000000001,
    },
    "[Liquor] Espresso Martini": {
        "blue ice espresso martini": 5.0,
    },
    "[Liquor] Espresso Shot": {
        "blue ice espresso martini": 3.0,
    },
    "[Liquor] Firecracker Flavor": {
        "LIQ Blue Curacao": 0.375,
    },
    "[Liquor] Firecracker Flavor 24oz TO GO": {
        "LIQ Blue Curacao": 0.8999999999999999,
    },
    "[Liquor] Gimlet Vodka": {
        "VODKA Well": 1.5,
    },
    "[Liquor] Grateful Flavor": {
        "LIQ Blue Curacao": 0.1875,
        "LIQ Chambord": 0.1875,
    },
    "[Liquor] Green Tea": {
        "WHISKEY Jameson": 1.125,
        "LIQ Peach Schnapps": 0.375,
    },
    "[Liquor] Lemon Drop": {
        "VODKA Well": 1.125,
        "LIQ Triple Sec": 0.375,
    },
    "[Liquor] Long Island": {
        "VODKA Well": 0.5,
        "GIN Well": 0.5,
        "RUM Well": 0.5,
        "TEQUILA Well": 0.5,
        "LIQ Triple Sec": 0.5,
    },
    "[Liquor] Margarita": {
        "TEQUILA Well": 1.5,
        "LIQ Triple Sec": 0.375,
    },
    "[Liquor] Martini Up": {
        "VODKA Well": 2.25,
        "LIQ Vermouth Dry": 0.375,
    },
    "[Liquor] Old Fashion": {
        "WHISKEY Well": 1.5,
        "BAR CONS Simple Syrup": 0.25,
        "BAR CONS Bitters": 0.1,
    },
    "[Liquor] TO GO RITA 16oz": {
        "TEQUILA Well": 2.24,
        "LIQ Triple Sec": 1.504,
    },
    "[Liquor] TO GO RITA 24oz": {
        "TEQUILA Well": 3.36,
        "LIQ Triple Sec": 2.256,
    },
    "[Liquor] White Tea": {
        "VODKA Well": 0.75,
        "RUM Malibu Coconut": 0.75,
        "LIQ Chambord": 0.5,
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
