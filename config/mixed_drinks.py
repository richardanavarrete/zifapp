# config/mixed_drinks.py
# Mixed drink recipes - ingredient -> oz per drink

from .constants import COUNT_OZ, STANDARD_POUR_OZ, REDBULL_MIXER_OZ

# Standard mixed drink recipes from the Drinks & Shots Build Guide
# Format: "Drink Name": {"Inventory Item": oz_per_drink}
MIXED_DRINK_RECIPES = {
    # ============ FROM BUILD GUIDE ============
    
    "AMF": {
        "VODKA Well": COUNT_OZ,
        "GIN Well": COUNT_OZ,
        "RUM Well": COUNT_OZ,
        "LIQ Blue Curacao": COUNT_OZ,
    },
    
    "Adios MF": {
        "VODKA Well": 0.5,
        "GIN Well": 0.5,
        "RUM Well": 0.5,
        "TEQUILA Well": 0.5,
        "LIQ Blue Curacao": 0.5,
    },
    
    "Appletini": {
        "VODKA Well": STANDARD_POUR_OZ,
        "LIQ Sour Apple": 0.75,
    },
    
    "Bahama Mama": {
        "RUM Malibu Coconut": 0.75,
        "RUM Bacardi Superior White": 0.75,
    },
    
    "Bay Breeze": {
        "VODKA Well": STANDARD_POUR_OZ,
    },
    
    "B-52": {
        "LIQ Kahlua": 0.75,
        "LIQ Baileys Irish Cream": 0.75,
        "LIQ Grand Marnier": 0.75,
    },
    
    "Blonde Slut": {
        "LIQ Jagermeister": 1.125,
        "LIQ Peach Schnapps": COUNT_OZ,
    },
    
    "Blue Hawaiian": {
        "RUM Well": 0.75,
        "VODKA Well": 0.75,
        "LIQ Blue Curacao": COUNT_OZ,
    },
    
    "Bloody Mary": {
        "VODKA Well": STANDARD_POUR_OZ,
        "BAR CONS Bloody Mary": 6.0,
    },
    
    "Cadillac Margarita": {
        "TEQUILA Patron Silver": STANDARD_POUR_OZ,
        "LIQ Grand Marnier": COUNT_OZ,
    },
    
    "Cherry Limeade": {
        "VODKA Fleischmann's Cherry": STANDARD_POUR_OZ,
    },
    
    "Chili Bomber": {
        "WHISKEY Crown Royal": STANDARD_POUR_OZ,
        "JUICE Red Bull": REDBULL_MIXER_OZ,
    },
    
    "Cosmo": {
        "VODKA Well": STANDARD_POUR_OZ,
        "LIQ Triple Sec": 0.75,
    },
    
    "Desert Donkey Milagro": {
        "TEQUILA Milagro Silver": STANDARD_POUR_OZ,
        "JUICE Ginger Beer": 4.0,
    },
    
    "Desert Donkey Titos": {
        "VODKA Titos": STANDARD_POUR_OZ,
        "JUICE Ginger Beer": 4.0,
    },
    
    "Espresso Martini": {
        "VODKA Well": STANDARD_POUR_OZ,
        "LIQ Kahlua": 0.75,
    },
    
    "Gimlet Vodka": {
        "VODKA Well": STANDARD_POUR_OZ,
    },
    
    "Grape Gatorade": {
        "VODKA Fleischmann's Grape": 1.125,
        "LIQ Blue Curacao": COUNT_OZ,
    },
    
    "Green Tea": {
        "WHISKEY Jameson": 1.125,
        "LIQ Peach Schnapps": COUNT_OZ,
    },
    
    "Gummy Bear": {
        "VODKA Western Son Raspberry": 1.125,
        "LIQ Peach Schnapps": COUNT_OZ,
    },
    
    "Lemon Drop": {
        "VODKA Well": 1.125,
        "LIQ Triple Sec": COUNT_OZ,
    },
    
    "Liquid Marijuana": {
        "LIQ Melon": COUNT_OZ,
        "LIQ Blue Curacao": COUNT_OZ,
        "RUM Malibu Coconut": COUNT_OZ,
        "RUM Captain Morgan Spiced": COUNT_OZ,
    },
    
    "Long Beach Tea": {
        "VODKA Well": COUNT_OZ,
        "GIN Well": COUNT_OZ,
        "RUM Well": COUNT_OZ,
        "LIQ Triple Sec": COUNT_OZ,
    },
    
    "Long Island": {
        "VODKA Well": 0.5,
        "GIN Well": 0.5,
        "RUM Well": 0.5,
        "TEQUILA Well": 0.5,
        "LIQ Triple Sec": 0.5,
    },
    
    "Manhattan": {
        "WHISKEY Well": STANDARD_POUR_OZ,
        "LIQ Vermouth Sweet": 0.75,
        "BAR CONS Bitters": 0.1,
    },
    
    "Margarita": {
        "TEQUILA Well": STANDARD_POUR_OZ,
        "LIQ Triple Sec": COUNT_OZ,
    },
    
    "Martini": {
        "VODKA Well": 2.25,  # 6 count
        "LIQ Vermouth Dry": COUNT_OZ,
    },
    
    "Martini Up": {
        "VODKA Well": 2.25,
        "LIQ Vermouth Dry": COUNT_OZ,
    },
    
    "Moscow Mule Titos": {
        "VODKA Titos": STANDARD_POUR_OZ,
        "JUICE Ginger Beer": 4.0,
    },
    
    "Old Fashion": {
        "WHISKEY Well": STANDARD_POUR_OZ,
        "BAR CONS Simple Syrup": 0.25,
        "BAR CONS Bitters": 0.1,
    },
    
    "Old Fashion Bulleit Rye": {
        "WHISKEY Bulleit Straight Rye": STANDARD_POUR_OZ,
        "BAR CONS Simple Syrup": 0.25,
        "BAR CONS Bitters": 0.1,
    },
    
    # Pineapple Upside Down Cake - uses vanilla vodka (86'd)
    # Will flag as unmatched if ordered
    
    "Pink Pussy": {
        "VODKA Well": 0.75,
        "LIQ Watermelon Schnapps": 0.75,
    },
    
    "Pink Starburst": {
        # Uses Absolut Vanilla (86'd) - only watermelon tracked
        "LIQ Watermelon Schnapps": COUNT_OZ,
    },
    
    "Purple Hooter": {
        "VODKA Well": 0.75,
        "LIQ Chambord": 0.75,
    },
    
    "Red Headed Slut": {
        "LIQ Jagermeister": 1.125,
        "LIQ Peach Schnapps": COUNT_OZ,
    },
    
    "Scooby Snack": {
        "RUM Malibu Coconut": 0.75,
        "LIQ Melon": 0.75,
    },
    
    "Sea Breeze": {
        "VODKA Well": STANDARD_POUR_OZ,
    },
    
    "Sex on the Beach": {
        "VODKA Well": 0.75,
        "LIQ Peach Schnapps": 0.75,
    },
    
    "Tequila Sunrise": {
        "TEQUILA Well": STANDARD_POUR_OZ,
    },
    
    "Titos Bloody": {
        "VODKA Titos": STANDARD_POUR_OZ,
        "BAR CONS Bloody Mary": 6.0,
    },
    
    "Titos Screw": {
        "VODKA Titos": STANDARD_POUR_OZ,
    },
    
    "Vegas Bomb": {
        "WHISKEY Crown Royal": 1.125,
        "LIQ Peach Schnapps": COUNT_OZ,
        "JUICE Red Bull": REDBULL_MIXER_OZ,
    },
    
    "Washington Apple": {
        "WHISKEY Crown Royal": 1.125,
        "LIQ Sour Apple": COUNT_OZ,
    },
    
    "White Gummy Bear": {
        # Uses vanilla vodka (86'd) - only peach tracked
        "LIQ Peach Schnapps": COUNT_OZ,
    },
    
    "White Russian": {
        "VODKA Well": 1.125,
        "LIQ Kahlua": COUNT_OZ,
    },
    
    "White Tea": {
        "VODKA Well": 0.75,
        "RUM Malibu Coconut": 0.75,
        "LIQ Chambord": 0.5,
    },
    "Zippa Rona": {
        "Frozen Margarita Batch": 16.0,  # The 16oz of slush
        "Coronita": 1.0                  # The full bottle of beer
    },
}

# Items that use 86'd products (vanilla vodka) - will flag if sold
DRINKS_WITH_86D_PRODUCTS = [
    "Pineapple Upside Down Cake",  # vanilla vodka
    "Pink Starburst",  # Absolut vanilla (partial)
    "White Gummy Bear",  # vanilla vodka (partial)
]
