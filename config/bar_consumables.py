# config/bar_consumables.py
# Bar consumables and mixers mapping

# Format: "Sales Mix Pattern": "Inventory Item Name"
BAR_CONSUMABLES_MAP = {
    # Bloody Mary Mix
    "Bloody Mary": "BAR CONS Bloody Mary",

    # Ginger Beer (for mules)
    "Ginger Beer": "JUICE Ginger Beer",

    # Red Bull variants
    "Red Bull": "JUICE Red Bull",
    "Red Bull SF": "JUICE Red Bull SF",
    "Red Bull Sugar Free": "JUICE Red Bull SF",
    "Red Bull Yellow": "JUICE Red Bull Yellow",

    # Other mixers
    "Mango Puree": "BAR CONS Mango Puree",
    "Simple Syrup": "BAR CONS Simple Syrup",
    "Bitters": "BAR CONS Bitters",
}

# Standard usage amounts for bar consumables (in oz)
BAR_CONS_USAGE = {
    "BAR CONS Bloody Mary": 6.0,  # Per bloody mary
    "JUICE Ginger Beer": 4.0,  # Per mule
    "JUICE Red Bull": 6.0,  # Half can per mixer
    "JUICE Red Bull SF": 6.0,
    "JUICE Red Bull Yellow": 6.0,
    "BAR CONS Mango Puree": 1.0,  # Per mango marg
    "BAR CONS Simple Syrup": 0.25,  # Per old fashion
    "BAR CONS Bitters": 0.1,  # Per old fashion/manhattan (dashes)
}

# Bottle/Can sizes for bar consumables (in oz)
# Used to convert theoretical usage from oz to bottles/cans to match bevweekly sheet units
BAR_CONS_BOTTLE_SIZES = {
    "BAR CONS Bloody Mary": 33.814,  # 1 liter bottle
    "BAR CONS Mango Puree": 33.814,  # 1 liter bottle
    "BAR CONS Simple Syrup": 33.814,  # 1 liter bottle
    "BAR CONS Bitters": 16.0,  # 16 oz bottle
    "JUICE Ginger Beer": 7.5,  # 7.5 oz can
    "JUICE Red Bull": 8.4,  # 8.4 oz can (standard)
    "JUICE Red Bull SF": 8.4,  # 8.4 oz can
    "JUICE Red Bull Yellow": 12.0,  # 12 oz can (yellow edition)
}

