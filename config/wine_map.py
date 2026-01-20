# config/wine_map.py
# Maps Sales Mix wine names to inventory items

# Format: "Sales Mix Pattern": "Inventory Item Name"
WINE_MAP = {
    # Champagne/Sparkling
    "Champagne GL": "WINE William Wycliff Brut Chateauamp",
    "Champagne": "WINE William Wycliff Brut Chateauamp",

    "La Marca Prosecco": "WINE LaMarca Prosecco",
    "Prosecco": "WINE LaMarca Prosecco",

    # House Wines (Salmon Creek)
    "House Cab GL": "WINE Salmon Creek Cab",
    "House Cab": "WINE Salmon Creek Cab",
    "20 Acres Cab": "WINE Salmon Creek Cab",  # Assuming same inventory

    "House Chard GL": "WINE Salmon Creek Chard",
    "House Chard": "WINE Salmon Creek Chard",

    "House Merlot GL": "WINE Salmon Creek Merlot",
    "House Merlot": "WINE Salmon Creek Merlot",

    "White Zin": "WINE Salmon Creek White Zin",

    # Premium Wines
    "Infamous Goose": "WINE Infamous Goose Sauv Blanc",
    "Sauvignon Blanc": "WINE Infamous Goose Sauv Blanc",

    "Kendall Jackson": "WINE Kendall Jackson Chardonnay",
    "Kendall Jackson Chard": "WINE Kendall Jackson Chardonnay",

    "La Crema Chard": "WINE La Crema Chardonnay",
    "La Crema Chardonnay": "WINE La Crema Chardonnay",

    "La Crema Pinot": "WINE La Crema Pinot Noir",
    "La Crema Pinot Noir": "WINE La Crema Pinot Noir",

    "Troublemaker": "WINE Troublemaker Red",

    "Villa Sandi": "WINE Villa Sandi Pinot Grigio",
    "Pinot Grigio": "WINE Villa Sandi Pinot Grigio",

    # Mixed drinks using wine
    "Mimosa": "WINE William Wycliff Brut Chateauamp",  # Uses champagne
}

# Wine pour sizes
WINE_GLASS_OZ = 5
WINE_BOTTLE_OZ = 25.36  # 750ml
