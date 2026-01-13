"""
Mappings Module - Vendor, Category, and Location mappings.

This module centralizes all item classification logic that was previously
embedded in zifapp.py lines 166-194.
"""

import json
from typing import Dict, List
from models import Item, InventoryDataset


# Vendor mapping (extracted from zifapp.py lines 166-172)
VENDOR_MAP = {
    "Breakthru": [
        "WHISKEY Buffalo Trace", "WHISKEY Bulleit Straight Rye", "WHISKEY Crown Royal",
        "WHISKEY Crown Royal Regal Apple", "WHISKEY Fireball Cinnamon", "WHISKEY Jack Daniels Black",
        "WHISKEY Jack Daniels Tennessee Fire", "VODKA Deep Eddy Lime", "VODKA Deep Eddy Orange",
        "VODKA Deep Eddy Ruby Red", "VODKA Fleischmann's Cherry", "VODKA Fleischmann's Grape",
        "VODKA Ketel One", "VODKAA Blue Ice Double Espresso", "LIQ Amaretto", "LIQ Baileys Irish Cream",
        "LIQ Chambord", "LIQ Melon", "LIQ Rumpleminze", "LIQ Triple Sec", "LIQ Blue Curacao",
        "LIQ Butterscotch", "LIQ Peach Schnapps", "LIQ Sour Apple", "LIQ Watermelon Schnapps",
        "BRANDY Well", "GIN Well", "RUM Well", "SCOTCH Well", "TEQUILA Well", "VODKA Well",
        "WHISKEY Well", "GIN Tanqueray", "TEQUILA Casamigos Blanco", "TEQUILA Corazon Reposado",
        "TEQUILA Don Julio Blanco", "RUM Captain Morgan Spiced", "WINE LaMarca Prosecco",
        "WINE William Wycliff Brut Chateauamp", "BAR CONS Bloody Mary", "JUICE Red Bull",
        "JUICE Red Bull SF", "JUICE Red Bull Yellow"
    ],
    "Southern": [
        "WHISKEY Basil Hayden", "WHISKEY Jameson", "WHISKEY Jim Beam", "WHISKEY Makers Mark",
        "WHISKEY Skrewball Peanut Butter", "VODKA Grey Goose", "VODKA Titos",
        "TEQUILA Cazadores Reposado", "TEQUILA Patron Silver", "RUM Bacardi Superior White",
        "RUM Malibu Coconut", "WHISKEY Dewars White Label", "WHISKEY Glenlivet",
        "LIQ Grand Marnier", "LIQ Jagermeister", "LIQ Kahlua", "LIQ Vermouth Dry",
        "LIQ Vermouth Sweet", "WINE Kendall Jackson Chardonnay", "WINE La Crema Chardonnay",
        "WINE La Crema Pinot Noir", "WINE Troublemaker Red", "WINE Villa Sandi Pinot Grigio",
        "BAR CONS Bitters", "BAR CONS Simple Syrup"
    ],
    "RNDC": [
        "WHISKEY Four Roses", "GIN Hendricks", "TEQUILA Milagro Anejo", "TEQUILA Milagro Reposado",
        "TEQUILA Milagro Silver", "WINE Infamous Goose Sauv Blanc", "WINE Salmon Creek Cab",
        "WINE Salmon Creek Chard", "WINE Salmon Creek Merlot", "WINE Salmon Creek White Zin",
        "BAR CONS Mango Puree"
    ],
    "Crescent": [
        "BEER DFT Alaskan Amber", "BEER DFT Blue Moon Belgian White", "BEER DFT Coors Light",
        "BEER DFT Dos Equis Lager", "BEER DFT Miller Lite", "BEER DFT Modelo Especial",
        "BEER DFT New Belgium Juicy Haze IPA", "BEER BTL Coors Banquet", "BEER BTL Coors Light",
        "BEER BTL Miller Lite", "BEER BTL Angry Orchard Crisp Apple",
        "BEER BTL College Street Big Blue Van", "BEER BTL Corona NA", "BEER BTL Corona Extra",
        "BEER BTL Corona Premier", "BEER BTL Coronita Extra", "BEER BTL Dos Equis Lager",
        "BEER BTL Guinness", "BEER BTL Heineken 0.0", "BEER BTL Modelo Especial",
        "BEER BTL Pacifico", "BEER BTL Truly Pineapple", "BEER BTL Truly Wild Berry",
        "BEER BTL Twisted Tea", "BEER BTL White Claw Black Cherry", "BEER BTL White Claw Mango",
        "BEER BTL White Claw Peach", "JUICE Ginger Beer", "VODKA Western Son Blueberry",
        "VODKA Western Son Lemon", "VODKA Western Son Original", "VODKA Western Son Prickly Pear",
        "VODKA Western Son Raspberry"
    ],
    "Hensley": [
        "BEER DFT Bud Light", "BEER DFT Church Music", "BEER DFT Firestone Walker 805",
        "BEER DFT Michelob Ultra", "BEER DFT Mother Road Sunday Drive",
        "BEER DFT Mother Road Tower Station", "BEER BTL Bud Light", "BEER BTL Budweiser",
        "BEER BTL Michelob Ultra", "BEER BTL Austin Eastciders"
    ]
}


def load_vendor_map() -> Dict[str, List[str]]:
    """Load vendor mappings (currently hardcoded, could be from JSON later)."""
    return {vendor: [item.strip() for item in items]
            for vendor, items in VENDOR_MAP.items()}


def get_vendor_for_item(item_id: str) -> str:
    """Get vendor for a given item."""
    vendor_map = load_vendor_map()
    for vendor, items in vendor_map.items():
        if item_id.strip() in items:
            return vendor
    return "Unknown"


def get_category_for_item(item_id: str) -> str:
    """
    Determine category based on item name patterns.

    Extracted from zifapp.py lines 178-194.
    """
    upper_item = item_id.upper().strip()

    if "WELL" in upper_item:
        return "Well"
    elif "WHISKEY" in upper_item:
        return "Whiskey"
    elif "VODKA" in upper_item:
        return "Vodka"
    elif "GIN" in upper_item:
        return "Gin"
    elif "TEQUILA" in upper_item:
        return "Tequila"
    elif "RUM" in upper_item:
        return "Rum"
    elif "SCOTCH" in upper_item:
        return "Scotch"
    elif "LIQ" in upper_item and "SCHNAPPS" not in upper_item:
        return "Liqueur"
    elif "SCHNAPPS" in upper_item:
        return "Cordials"
    elif "WINE" in upper_item:
        return "Wine"
    elif "BEER DFT" in upper_item:
        return "Draft Beer"
    elif "BEER BTL" in upper_item:
        return "Bottled Beer"
    elif "JUICE" in upper_item:
        return "Juice"
    elif "BAR CONS" in upper_item:
        return "Bar Consumables"

    return "Unknown"


def load_inventory_layout() -> Dict[str, List[str]]:
    """Load physical location mapping from inventory_layout.json."""
    try:
        with open('inventory_layout.json', 'r') as f:
            layout = json.load(f)
            # Filter out null values
            return {location: [item for item in items if item is not None]
                    for location, items in layout.items()}
    except Exception:
        return {}


def get_location_for_item(item_id: str) -> str:
    """Get physical storage location for an item."""
    layout = load_inventory_layout()
    for location, items in layout.items():
        if item_id.strip() in items:
            return location
    return "Unknown"


def enrich_dataset(dataset: InventoryDataset) -> InventoryDataset:
    """
    Add vendor, category, and location metadata to all items.

    This replaces the inline mapping logic from zifapp.py.

    Args:
        dataset: InventoryDataset to enrich

    Returns:
        The same dataset (modified in place) with enriched item metadata
    """
    for item_id, item in dataset.items.items():
        item.vendor = get_vendor_for_item(item_id)
        item.category = get_category_for_item(item_id)
        item.location = get_location_for_item(item_id)

    return dataset


def get_items_by_vendor(dataset: InventoryDataset, vendor: str) -> List[str]:
    """Get all item IDs for a given vendor."""
    return [item_id for item_id, item in dataset.items.items()
            if item.vendor == vendor]


def get_items_by_category(dataset: InventoryDataset, category: str) -> List[str]:
    """Get all item IDs for a given category."""
    return [item_id for item_id, item in dataset.items.items()
            if item.category == category]


def get_all_vendors(dataset: InventoryDataset) -> List[str]:
    """Get list of all vendors present in the dataset."""
    vendors = set(item.vendor for item in dataset.items.values())
    vendors.discard("Unknown")
    return sorted(list(vendors))


def get_all_categories(dataset: InventoryDataset) -> List[str]:
    """Get list of all categories present in the dataset."""
    categories = set(item.category for item in dataset.items.values())
    categories.discard("Unknown")
    return sorted(list(categories))
