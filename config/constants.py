# config/constants.py
# Pour sizes, keg sizes, and conversion factors

# Pour measurements
COUNT_OZ = 0.375  # oz per 1 count
STANDARD_POUR_OZ = 1.5  # 4-count standard pour (shot)
BUMP_OZ = 0.375  # Bump/add-on pour (1 count)
FLAVOR_OZ=0.375 # Flavor/add-on pour (1 count)

# Keg sizes in oz
HALF_BARREL_OZ = 1984  # 15.5 gallon keg (most common)
KEG_50L_OZ = 1690  # 50L keg (Firestone Walker 805)
SIXTH_BARREL_OZ = 661  # 5.16 gallon keg
QUARTER_BARREL_OZ = 992  # 7.75 gallon keg

# Draft pour sizes
DRAFT_POUR_SIZES = {
    "16oz": 16,
    "32oz": 32,
    "Pitcher": 64,
    "Grwlr": 64,
    "Growler": 64,
}

# Bottle sizes (in ounces)
LIQUOR_BOTTLE_OZ = 33.8    # Updated to 1 Liter (standard for your bar)
LIQUOR_BOTTLE_750_OZ = 25.4 # Kept just in case you need it

WINE_BOTTLE_OZ = 25.4      # Standard 750ml
WINE_BOTTLE_MAGNUM_OZ = 50.7 # 1.5 Liter (for house wines)

# Renamed to match your other code
WINE_GLASS_OZ = 6.0        # Standard wine glass pour

# Canned beverages
REDBULL_CAN_OZ = 8.4
REDBULL_MIXER_OZ = 4  # half can per mixer drink

# Frozen Margarita batch calculations (12L total batch)
# Recipe: 3 bottles tequila + 2 bottles triple sec + fill to 16L with mix
ZIPPARITA_BATCH_TOTAL_OZ = 405.8  # 12L in oz
ZIPPARITA_TEQUILA_OZ = 101.4  # 3 × 1L bottles
ZIPPARITA_TRIPLE_SEC_OZ = 67.6  # 2 × 1L bottles
ZIPPARITA_TEQUILA_RATIO = ZIPPARITA_TEQUILA_OZ / ZIPPARITA_BATCH_TOTAL_OZ  # ~25%
ZIPPARITA_TRIPLE_SEC_RATIO = ZIPPARITA_TRIPLE_SEC_OZ / ZIPPARITA_BATCH_TOTAL_OZ  # ~9.4%

# Frozen margarita serving sizes
FROZEN_MARG_SIZES = {
    "Iceberg": 1,
    "Zipparita": 10,  # Standard 10oz pilsner
    "BIG Zipparita": 16,
    "TO GO RITA 16oz": 16,
    "TO GO RITA 24oz": 24,
}
