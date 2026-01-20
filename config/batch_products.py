"""
Configuration for batch products that need to be converted back to ingredient inventory.

When counting inventory, batched products (like pre-made margarita mix) should be
counted and converted back to their ingredient equivalents to accurately reflect
what's "in house" even though it's already mixed.
"""

from config.constants import LIQUOR_BOTTLE_OZ, ZIPPARITA_TEQUILA_RATIO, ZIPPARITA_TRIPLE_SEC_RATIO

# Define batch products and their ingredient breakdown
# Each batch product maps to a dict of {inventory_item: ratio}
BATCH_PRODUCTS = {
    'Milagro Marg On Tap': {
        'ingredients': {
            'TEQUILA Milagro Silver': ZIPPARITA_TEQUILA_RATIO,  # ~25%
            'LIQ Triple Sec': ZIPPARITA_TRIPLE_SEC_RATIO,  # ~16.7%
        },
        'unit': 'oz',  # Batch is measured in oz
        'description': 'Pre-made frozen margarita mix with Milagro Silver tequila'
    }
}


def convert_batch_to_ingredients(batch_name: str, batch_oz: float) -> dict:
    """
    Convert a batch volume back to ingredient bottle equivalents.

    Args:
        batch_name: Name of the batch product (e.g., 'Milagro Marg On Tap')
        batch_oz: Volume of remaining batch in ounces

    Returns:
        Dict mapping inventory item names to bottle quantities:
        {
            'TEQUILA Milagro Silver': 1.25,
            'LIQ Triple Sec': 0.47
        }
    """
    if batch_name not in BATCH_PRODUCTS:
        return {}

    batch_config = BATCH_PRODUCTS[batch_name]
    ingredient_bottles = {}

    for inv_item, ratio in batch_config['ingredients'].items():
        ingredient_oz = batch_oz * ratio
        bottles = ingredient_oz / LIQUOR_BOTTLE_OZ
        ingredient_bottles[inv_item] = round(bottles, 2)

    return ingredient_bottles


def get_batch_products() -> list:
    """Get list of all tracked batch product names."""
    return list(BATCH_PRODUCTS.keys())


def is_batch_product(item_name: str) -> bool:
    """Check if an item is a tracked batch product."""
    return item_name in BATCH_PRODUCTS
