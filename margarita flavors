# config/margarita_flavors.py
# Frozen margarita flavor additions (beyond base tequila/triple sec)

from .constants import COUNT_OZ

# Flavor additions for frozen margaritas
# Base frozen marg already uses well tequila + triple sec via batch ratios
# These are the ADDITIONAL ingredients for each flavor
# Format: "Flavor Name Pattern": {"Inventory Item": oz_per_drink}

MARGARITA_FLAVOR_ADDITIONS = {
    # Standard flavors (1 count of liqueur)
    "Chambord Flavor": {"LIQ Chambord": COUNT_OZ},
    "Blue Flavor": {"LIQ Blue Curacao": COUNT_OZ},
    "Gran Mar Flavor": {"LIQ Grand Marnier": COUNT_OZ},
    "Watermelon Flavor": {"LIQ Watermelon Schnapps": COUNT_OZ},
    "Peach Flavor": {"LIQ Peach Schnapps": COUNT_OZ},
    "Melon Flavor": {"LIQ Melon": COUNT_OZ},
    "Amaretto Flavor": {"LIQ Amaretto": COUNT_OZ},
    
    # Non-liquor flavors
    "Mango Flavor": {"BAR CONS Mango Puree": 1.0},
    "Strawberry Flavor": {},  # Uses strawberry mix, no tracked liquor
    
    # Multi-ingredient flavors
    "Firecracker Flavor": {"LIQ Blue Curacao": COUNT_OZ},
    "Grateful Flavor": {"LIQ Blue Curacao": COUNT_OZ, "LIQ Chambord": COUNT_OZ},
    "Mary Jane Flavor": {"LIQ Blue Curacao": COUNT_OZ, "LIQ Melon": COUNT_OZ},
    "Missyrita Flavor": {"WINE Salmon Creek Merlot": COUNT_OZ, "LIQ Peach Schnapps": COUNT_OZ},
    
    # Premium tequila flavors - these REPLACE well tequila, not add to it
    # Handled specially in the parser - no triple sec ratio change, just tequila swap
    "Milagro Anejo Flavor": {},  # Uses Milagro Anejo instead of well
    "Milagro Silver Flavor": {},  # Uses Milagro Silver instead of well
}

# Flavors that use premium tequila instead of well
# When these are detected, use the specified tequila instead of TEQUILA Well
PREMIUM_TEQUILA_FLAVORS = {
    "Milagro Anejo Flavor": "TEQUILA Milagro Anejo",
    "Milagro Anejo": "TEQUILA Milagro Anejo",
    "Milagro Silver Flavor": "TEQUILA Milagro Silver",
    "Milagro Silver": "TEQUILA Milagro Silver",
}

# Size multipliers for different frozen marg sizes
# The base calculation uses 10oz (standard Zipparita)
FROZEN_SIZE_MULTIPLIERS = {
    10: 1.0,   # Standard Zipparita
    16: 1.6,   # BIG Zipparita, TO GO 16oz
    24: 2.4,   # TO GO 24oz
}
