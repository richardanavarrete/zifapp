"""
Bottle Weight Utilities - Default weights and fill level calculations.

Provides standard bottle/keg weights for calculating fill levels from scale readings.
"""

from typing import Dict, Tuple, Optional


# Standard bottle weights (in grams)
# Format: {unit_of_measure: (full_weight, empty_weight)}
DEFAULT_WEIGHTS = {
    # Liquor bottles
    "Bottle (750 mL)": (1240, 490),
    "Bottle (1 L)": (1540, 540),
    "Bottle (1.75 L)": (2400, 850),
    "Bottle (375 mL)": (720, 290),
    "Bottle (50 mL)": (110, 60),

    # Wine bottles
    "Wine Bottle (750 mL)": (1240, 490),
    "Wine Bottle (1.5 L)": (2100, 900),

    # Beer bottles
    "Bottle (12 oz)": (380, 210),
    "Bottle (355 mL)": (380, 210),
    "Bottle (22 oz)": (710, 350),

    # Kegs (in grams - user inputs pounds, we convert)
    "Keg (Half Barrel)": (72574, 13608),      # 160 lbs full, 30 lbs empty
    "Keg (Quarter Barrel)": (40823, 9072),    # 90 lbs full, 20 lbs empty
    "Keg (Sixth Barrel)": (29484, 6804),      # 65 lbs full, 15 lbs empty
    "Keg (Cornelius)": (10433, 4082),         # 23 lbs full, 9 lbs empty

    # Generic fallbacks
    "Bottle": (1240, 490),  # Assume 750ml
    "Keg": (72574, 13608),  # Assume half barrel
}

# Alternative name mappings
UNIT_ALIASES = {
    "bottle (1 l)": "Bottle (1 L)",
    "750ml": "Bottle (750 mL)",
    "750 ml": "Bottle (750 mL)",
    "1l": "Bottle (1 L)",
    "1 l": "Bottle (1 L)",
    "1.75l": "Bottle (1.75 L)",
    "half barrel": "Keg (Half Barrel)",
    "quarter barrel": "Keg (Quarter Barrel)",
    "sixth barrel": "Keg (Sixth Barrel)",
    "1/2 barrel": "Keg (Half Barrel)",
    "1/4 barrel": "Keg (Quarter Barrel)",
    "1/6 barrel": "Keg (Sixth Barrel)",
}

# Pounds to grams conversion
LBS_TO_GRAMS = 453.592


def get_default_weights(unit_of_measure: str) -> Dict[str, float]:
    """
    Get default full and empty weights for a unit of measure.

    Args:
        unit_of_measure: Unit string (e.g., "Bottle (750 mL)", "Keg")

    Returns:
        Dict with 'full' and 'empty' weights in grams
    """
    # Try exact match first
    if unit_of_measure in DEFAULT_WEIGHTS:
        full, empty = DEFAULT_WEIGHTS[unit_of_measure]
        return {'full': full, 'empty': empty}

    # Try case-insensitive match
    unit_lower = unit_of_measure.lower()
    if unit_lower in UNIT_ALIASES:
        canonical = UNIT_ALIASES[unit_lower]
        full, empty = DEFAULT_WEIGHTS[canonical]
        return {'full': full, 'empty': empty}

    # Try partial match for "keg" or "bottle"
    if 'keg' in unit_lower:
        full, empty = DEFAULT_WEIGHTS["Keg"]
        return {'full': full, 'empty': empty}
    elif 'bottle' in unit_lower or 'btl' in unit_lower:
        full, empty = DEFAULT_WEIGHTS["Bottle"]
        return {'full': full, 'empty': empty}

    # Default to standard 750ml bottle
    return {'full': 1240, 'empty': 490}


def is_keg(unit_of_measure: str) -> bool:
    """Check if the unit of measure is a keg."""
    return 'keg' in unit_of_measure.lower()


def pounds_to_grams(pounds: float) -> float:
    """Convert pounds to grams."""
    return pounds * LBS_TO_GRAMS


def grams_to_pounds(grams: float) -> float:
    """Convert grams to pounds."""
    return grams / LBS_TO_GRAMS


def calculate_fill_from_weight(
    current_weight: float,
    full_weight: Optional[float] = None,
    empty_weight: Optional[float] = None,
    unit_of_measure: str = "Bottle",
    input_unit: str = "grams"
) -> Tuple[float, Dict[str, float]]:
    """
    Calculate fill percentage from current weight.

    Args:
        current_weight: Current weight (in grams or pounds)
        full_weight: Full bottle/keg weight (in grams, optional)
        empty_weight: Empty bottle/keg weight (in grams, optional)
        unit_of_measure: Type of container
        input_unit: "grams" or "pounds"

    Returns:
        Tuple of (fill_percentage, weights_dict)
        - fill_percentage: 0.0 to 1.0
        - weights_dict: {'full': X, 'empty': Y, 'current': Z} in grams
    """
    # Convert input to grams if needed
    if input_unit == "pounds":
        current_weight_grams = pounds_to_grams(current_weight)
    else:
        current_weight_grams = current_weight

    # Get default weights if not provided
    if full_weight is None or empty_weight is None:
        defaults = get_default_weights(unit_of_measure)
        full_weight = full_weight or defaults['full']
        empty_weight = empty_weight or defaults['empty']

    # Calculate fill percentage
    liquid_weight = current_weight_grams - empty_weight
    full_liquid_weight = full_weight - empty_weight

    if full_liquid_weight <= 0:
        return 0.0, {'full': full_weight, 'empty': empty_weight, 'current': current_weight_grams}

    fill_percentage = liquid_weight / full_liquid_weight

    # Clamp between 0 and 1
    fill_percentage = max(0.0, min(1.0, fill_percentage))

    return fill_percentage, {
        'full': full_weight,
        'empty': empty_weight,
        'current': current_weight_grams
    }


def format_weight_display(weight_grams: float, is_keg_item: bool = False) -> str:
    """
    Format weight for display (grams for bottles, pounds for kegs).

    Args:
        weight_grams: Weight in grams
        is_keg_item: True if this is a keg

    Returns:
        Formatted string (e.g., "850g" or "65 lbs")
    """
    if is_keg_item:
        pounds = grams_to_pounds(weight_grams)
        return f"{pounds:.1f} lbs"
    else:
        return f"{weight_grams:.0f}g"


def get_weight_ranges(unit_of_measure: str) -> Dict[str, Tuple[float, float]]:
    """
    Get expected weight ranges for validation.

    Returns:
        Dict with 'grams' and 'pounds' ranges: (min, max)
    """
    weights = get_default_weights(unit_of_measure)
    is_keg_item = is_keg(unit_of_measure)

    # Add 10% buffer for variations
    min_weight = weights['empty'] * 0.9
    max_weight = weights['full'] * 1.1

    return {
        'grams': (min_weight, max_weight),
        'pounds': (grams_to_pounds(min_weight), grams_to_pounds(max_weight)),
        'is_keg': is_keg_item
    }
