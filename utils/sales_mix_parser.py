"""
Sales Mix Parser - Robust GEMpos CSV Parser
Handles varying column positions and nesting levels automatically.
"""
import pandas as pd
import re
import sys
import os

# --- Add Project Root to Path ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config.constants import (
    COUNT_OZ, STANDARD_POUR_OZ, HALF_BARREL_OZ, LIQUOR_BOTTLE_OZ, KEG_50L_OZ,
    DRAFT_POUR_SIZES, ZIPPARITA_TEQUILA_RATIO, ZIPPARITA_TRIPLE_SEC_RATIO,
    WINE_GLASS_OZ, WINE_BOTTLE_OZ, LIQUOR_BOTTLE_750_OZ, WINE_BOTTLE_MAGNUM_OZ
)
from config.draft_beer_map import DRAFT_BEER_MAP, DRAFT_SKIP_ITEMS
from config.bottle_beer_map import BOTTLE_BEER_MAP
from config.liquor_map import LIQUOR_MAP
from config.wine_map import WINE_MAP
from config.mixed_drinks import MIXED_DRINK_RECIPES
from config.margarita_flavors import MARGARITA_FLAVOR_ADDITIONS, PREMIUM_TEQUILA_FLAVORS
from config.bar_consumables import BAR_CONSUMABLES_MAP
from config.manual_overrides import MANUAL_MAPPINGS, ENABLE_MANUAL_MAPPINGS


def find_marker_position(row):
    """
    Find where [+] marker is in the row and return (marker_col, name_col, nesting_level).
    Returns (None, None, None) if no marker found.
    
    Nesting levels:
      - Level 0: [+] in column 0 = top category (Bottle, Draft, Liquor, Wine, Food)
      - Level 1: [+] in column 1 = subcategory under Food (Add, Appetizers, etc.)
      - Level 2: [+] in column 2 = sub-subcategory (Mixed Drinks, Whiskey, Vodka, etc.)
    """
    for col_idx in range(min(6, len(row))):
        val = row.iloc[col_idx] if col_idx < len(row) else None
        if pd.notna(val) and str(val).strip() == '[+]':
            # The name follows the [+] marker
            name_col = col_idx + 1
            if name_col < len(row) and pd.notna(row.iloc[name_col]):
                return col_idx, name_col, col_idx
    return None, None, None


def find_item_name(row, start_col=0):
    """
    Find the first non-empty, non-marker text in the row starting from start_col.
    Skip numeric-only values (like Item IDs).
    """
    for col_idx in range(start_col, min(8, len(row))):  # Don't go past column 7
        val = row.iloc[col_idx] if col_idx < len(row) else None
        if pd.notna(val):
            val_str = str(val).strip()
            # Skip [+] markers, empty strings, and pure numbers (Item IDs)
            if val_str and val_str != '[+]' and not val_str.replace(',', '').replace('.', '').isdigit():
                return val_str
    return None


def find_qty_column(df, header_row_idx):
    """Find the Qty column dynamically."""
    header_row = df.iloc[header_row_idx]
    for i, val in enumerate(header_row):
        if pd.notna(val) and str(val).strip() == 'Qty':
            return i
    # Fallback: usually column 8
    return 8


def find_amount_column(df, header_row_idx):
    """Find the Amount column dynamically."""
    header_row = df.iloc[header_row_idx]
    for i, val in enumerate(header_row):
        if pd.notna(val) and str(val).strip() == 'Amount':
            return i
    # Fallback: usually column 9
    return 9


def parse_sales_mix_csv(uploaded_csv):
    """
    Parse any GEMpos Sales Mix CSV into a structured DataFrame.
    
    Automatically detects:
    - Header row location
    - Category/subcategory markers at any nesting level
    - Item names in varying column positions
    - Qty and Amount column positions
    
    Returns DataFrame with columns: Category, Subcategory, Item, Qty, Amount
    """
    # Read the CSV
    df = pd.read_csv(uploaded_csv, header=None)
    
    # Find the header row (contains "Qty")
    header_row_idx = None
    for idx, row in df.iterrows():
        row_str = ','.join(str(v) for v in row if pd.notna(v))
        if 'Qty' in row_str:
            header_row_idx = idx
            break
    
    if header_row_idx is None:
        raise ValueError("Could not find header row with 'Qty' column in CSV")
    
    # Get column positions
    qty_col = find_qty_column(df, header_row_idx)
    amount_col = find_amount_column(df, header_row_idx)
    
    # Parse the data rows
    parsed_items = []
    
    # Track hierarchy - can have multiple levels
    # Level 0 = top category, Level 1 = subcategory, Level 2 = sub-subcategory
    hierarchy = {0: None, 1: None, 2: None}
    
    for idx in range(header_row_idx + 1, len(df)):
        row = df.iloc[idx]
        
        # Check for end of data
        row_values = [str(v) for v in row if pd.notna(v)]
        row_str = ' '.join(row_values)
        if 'Grand Total' in row_str:
            break
        
        # Check for category/subcategory markers
        marker_col, name_col, level = find_marker_position(row)
        
        if marker_col is not None:
            # This is a category/subcategory header row
            category_name = str(row.iloc[name_col]).strip() if name_col < len(row) else None
            hierarchy[level] = category_name
            
            # Clear deeper levels when we encounter a new category at this level
            for deeper_level in range(level + 1, 3):
                hierarchy[deeper_level] = None
            
            continue
        
        # This should be an item row - find the item name
        item_name = find_item_name(row)
        
        if not item_name:
            continue
        
        # Get quantity
        qty = 0
        if qty_col < len(row) and pd.notna(row.iloc[qty_col]):
            try:
                qty_str = str(row.iloc[qty_col]).replace(',', '')
                qty = int(float(qty_str))
            except (ValueError, TypeError):
                qty = 0
        
        # Get amount
        amount = 0.0
        if amount_col < len(row) and pd.notna(row.iloc[amount_col]):
            try:
                amt_str = str(row.iloc[amount_col]).replace('$', '').replace(',', '')
                amount = float(amt_str)
            except (ValueError, TypeError):
                amount = 0.0
        
        # Only include items with qty > 0
        if qty > 0:
            # Determine category and subcategory from hierarchy
            # Level 0 is always the main category
            # Levels 1+ are subcategories (we'll combine them if needed)
            main_category = hierarchy.get(0)
            
            # For subcategory, prefer the deepest non-None level
            subcategory = None
            for level in [2, 1]:
                if hierarchy.get(level):
                    subcategory = hierarchy[level]
                    break
            
            parsed_items.append({
                'Category': main_category,
                'Subcategory': subcategory,
                'Item': item_name,
                'Qty': qty,
                'Amount': amount,
            })
    
    result_df = pd.DataFrame(parsed_items)
    
    # Debug info
    if len(result_df) > 0:
        categories = result_df['Category'].unique().tolist()
        subcategories = result_df['Subcategory'].dropna().unique().tolist()
        print(f"Parsed {len(result_df)} items")
        print(f"Categories: {categories}")
        print(f"Subcategories: {subcategories}")
    
    return result_df


def calculate_draft_beer_usage(sales_df, runtime_mappings=None):
    """Calculate theoretical keg usage from draft beer sales."""
    results = {}
    unmatched = []

    all_manual_mappings = dict(MANUAL_MAPPINGS)
    if runtime_mappings:
        all_manual_mappings.update(runtime_mappings)

    draft_sales = sales_df[sales_df['Category'] == 'Draft'].copy()

    for _, row in draft_sales.iterrows():
        item_name = row['Item']
        qty = row['Qty']

        # Check manual overrides first
        if ENABLE_MANUAL_MAPPINGS and item_name in all_manual_mappings:
            for inv_item, oz_per_item in all_manual_mappings[item_name].items():
                if inv_item not in results:
                    results[inv_item] = {'total_oz': 0, 'keg_size': HALF_BARREL_OZ, 'kegs_used': 0, 'items': []}
                oz_used = qty * oz_per_item
                results[inv_item]['total_oz'] += oz_used
                results[inv_item]['kegs_used'] = results[inv_item]['total_oz'] / results[inv_item]['keg_size']
                results[inv_item]['items'].append(f"{item_name}: {qty} × {oz_per_item}oz [MANUAL]")
            continue

        # Skip non-beer items
        if any(skip in item_name for skip in DRAFT_SKIP_ITEMS):
            continue

        # Determine pour size
        pour_oz = 16  # default
        for size_name, size_oz in DRAFT_POUR_SIZES.items():
            if size_name in item_name:
                pour_oz = size_oz
                break

        # Find matching inventory item
        matched = False
        for pattern, (inv_item, keg_size) in DRAFT_BEER_MAP.items():
            if pattern.lower() in item_name.lower():
                total_oz = qty * pour_oz
                if inv_item not in results:
                    results[inv_item] = {'total_oz': 0, 'keg_size': keg_size, 'kegs_used': 0, 'items': []}
                results[inv_item]['total_oz'] += total_oz
                results[inv_item]['kegs_used'] = results[inv_item]['total_oz'] / keg_size
                results[inv_item]['items'].append(f"{item_name}: {qty} × {pour_oz}oz")
                matched = True
                break

        if not matched:
            unmatched.append(f"{item_name} (qty: {qty})")

    return results, unmatched


def calculate_bottle_beer_usage(sales_df, runtime_mappings=None):
    """Calculate theoretical bottle/can usage."""
    results = {}
    unmatched = []

    all_manual_mappings = dict(MANUAL_MAPPINGS)
    if runtime_mappings:
        all_manual_mappings.update(runtime_mappings)

    bottle_sales = sales_df[sales_df['Category'] == 'Bottle'].copy()

    for _, row in bottle_sales.iterrows():
        item_name = row['Item']
        qty = row['Qty']

        if ENABLE_MANUAL_MAPPINGS and item_name in all_manual_mappings:
            for inv_item, count_per_item in all_manual_mappings[item_name].items():
                if inv_item not in results:
                    results[inv_item] = {'qty': 0, 'items': []}
                results[inv_item]['qty'] += qty * count_per_item
                results[inv_item]['items'].append(f"{item_name}: {qty} × {count_per_item} [MANUAL]")
            continue

        # Clean up item name
        clean_name = re.sub(r'\s*\(FS\)\s*$', '', item_name).strip()

        matched = False
        for pattern, inv_item in BOTTLE_BEER_MAP.items():
            if pattern.lower() in clean_name.lower():
                if inv_item not in results:
                    results[inv_item] = {'qty': 0, 'items': []}
                results[inv_item]['qty'] += qty
                results[inv_item]['items'].append(f"{item_name}: {qty}")
                matched = True
                break

        if not matched:
            unmatched.append(f"{item_name} (qty: {qty})")

    return results, unmatched


def calculate_liquor_usage(sales_df, runtime_mappings=None):
    """Calculate theoretical liquor bottle usage from straight pours."""
    results = {}
    unmatched = []

    all_manual_mappings = dict(MANUAL_MAPPINGS)
    if runtime_mappings:
        all_manual_mappings.update(runtime_mappings)

    # Get liquor items - Category == 'Liquor' but NOT Mixed Drinks
    # This includes subcategories like Bourbon & Whiskey, Vodka, Gin, Tequila, Rum, Scotch, Cordials, Bar Other
    liquor_sales = sales_df[
        (sales_df['Category'] == 'Liquor') & 
        (sales_df['Subcategory'] != 'Mixed Drinks')
    ].copy()

    for _, row in liquor_sales.iterrows():
        item_name = row['Item']
        qty = row['Qty']

        if ENABLE_MANUAL_MAPPINGS and item_name in all_manual_mappings:
            for inv_item, oz_per_drink in all_manual_mappings[item_name].items():
                if inv_item not in results:
                    results[inv_item] = {'oz': 0, 'bottles': 0, 'items': []}
                results[inv_item]['oz'] += qty * oz_per_drink
                results[inv_item]['bottles'] = results[inv_item]['oz'] / LIQUOR_BOTTLE_OZ
                results[inv_item]['items'].append(f"{item_name}: {qty} × {oz_per_drink}oz [MANUAL]")
            continue

        # Clean up item name
        clean_name = re.sub(r'\s*\(FS\)\s*$', '', item_name).strip()
        is_bump = '(Bump)' in item_name
        clean_name = re.sub(r'\s*\(Bump\)\s*$', '', clean_name).strip()

        pour_oz = COUNT_OZ if is_bump else STANDARD_POUR_OZ

        matched = False
        for pattern, inv_item in LIQUOR_MAP.items():
            if pattern.lower() in clean_name.lower():
                total_oz = qty * pour_oz
                if inv_item not in results:
                    results[inv_item] = {'oz': 0, 'bottles': 0, 'items': []}
                results[inv_item]['oz'] += total_oz
                results[inv_item]['bottles'] = results[inv_item]['oz'] / LIQUOR_BOTTLE_OZ
                results[inv_item]['items'].append(f"{item_name}: {qty} × {pour_oz}oz")
                matched = True
                break

        if not matched:
            unmatched.append(f"{item_name} (qty: {qty})")

    return results, unmatched


def calculate_wine_usage(sales_df, runtime_mappings=None):
    """Calculate theoretical wine bottle usage."""
    results = {}
    unmatched = []

    all_manual_mappings = dict(MANUAL_MAPPINGS)
    if runtime_mappings:
        all_manual_mappings.update(runtime_mappings)

    wine_sales = sales_df[sales_df['Category'] == 'Wine'].copy()

    for _, row in wine_sales.iterrows():
        item_name = row['Item']
        qty = row['Qty']

        if ENABLE_MANUAL_MAPPINGS and item_name in all_manual_mappings:
            for inv_item, oz_per_drink in all_manual_mappings[item_name].items():
                if inv_item not in results:
                    results[inv_item] = {'oz': 0, 'bottles': 0, 'items': []}
                results[inv_item]['oz'] += qty * oz_per_drink
                results[inv_item]['bottles'] = results[inv_item]['oz'] / WINE_BOTTLE_OZ
                results[inv_item]['items'].append(f"{item_name}: {qty} × {oz_per_drink}oz [MANUAL]")
            continue

        is_bottle = 'BTL' in item_name.upper() or 'Bottle' in item_name
        pour_oz = WINE_BOTTLE_OZ if is_bottle else WINE_GLASS_OZ

        matched = False
        for pattern, inv_item in WINE_MAP.items():
            if pattern.lower() in item_name.lower():
                total_oz = qty * pour_oz
                if inv_item not in results:
                    results[inv_item] = {'oz': 0, 'bottles': 0, 'items': []}
                results[inv_item]['oz'] += total_oz
                results[inv_item]['bottles'] = results[inv_item]['oz'] / WINE_BOTTLE_OZ
                results[inv_item]['items'].append(f"{item_name}: {qty} × {pour_oz}oz")
                matched = True
                break

        if not matched:
            unmatched.append(f"{item_name} (qty: {qty})")

    return results, unmatched


def calculate_mixed_drink_usage(sales_df, runtime_mappings=None):
    """Calculate theoretical usage from mixed drinks including frozen margaritas."""
    results = {}
    unmatched = []

    all_manual_mappings = dict(MANUAL_MAPPINGS)
    if runtime_mappings:
        all_manual_mappings.update(runtime_mappings)

    # Get mixed drinks - Subcategory == 'Mixed Drinks'
    mixed_sales = sales_df[sales_df['Subcategory'] == 'Mixed Drinks'].copy()

    for _, row in mixed_sales.iterrows():
        item_name = row['Item']
        qty = row['Qty']

        # Check manual overrides first
        if ENABLE_MANUAL_MAPPINGS and item_name in all_manual_mappings:
            for inv_item, oz_per_drink in all_manual_mappings[item_name].items():
                if inv_item not in results:
                    results[inv_item] = {'oz': 0, 'bottles': 0, 'items': []}
                results[inv_item]['oz'] += qty * oz_per_drink
                if 'JUICE' in inv_item or 'BAR CONS' in inv_item:
                    results[inv_item]['bottles'] = results[inv_item]['oz']
                else:
                    results[inv_item]['bottles'] = results[inv_item]['oz'] / LIQUOR_BOTTLE_OZ
                results[inv_item]['items'].append(f"{item_name}: {qty} × {oz_per_drink}oz [MANUAL]")
            continue

        # Clean up item name
        clean_name = re.sub(r'\s*\(FS\)\s*$', '', item_name).strip()
        
        # Check for frozen margarita variants
        is_frozen_marg = False
        frozen_size = 10
        
        # Detect frozen marg by name patterns
        if clean_name == 'Zipparita':
            is_frozen_marg = True
            frozen_size = 10
        elif clean_name == 'BIG Zipparita':
            is_frozen_marg = True
            frozen_size = 16
        elif 'TO GO RITA 16oz' in item_name:
            is_frozen_marg = True
            frozen_size = 16
        elif 'TO GO RITA 24oz' in item_name:
            is_frozen_marg = True
            frozen_size = 24
        elif 'Flavor' in item_name:
            is_frozen_marg = True
            if '24oz' in item_name:
                frozen_size = 24
            elif '16oz' in item_name or 'BIG' in item_name:
                frozen_size = 16
            else:
                frozen_size = 10
        elif 'Milagro Marg On Tap' in item_name:
            is_frozen_marg = True
            frozen_size = 10  # Standard on-tap size
            
            # Uses Milagro Silver instead of well
            tequila_oz = qty * frozen_size * ZIPPARITA_TEQUILA_RATIO
            triple_sec_oz = qty * frozen_size * ZIPPARITA_TRIPLE_SEC_RATIO
            
            inv_item = 'TEQUILA Milagro Silver'
            if inv_item not in results:
                results[inv_item] = {'oz': 0, 'bottles': 0, 'items': []}
            results[inv_item]['oz'] += tequila_oz
            results[inv_item]['bottles'] = results[inv_item]['oz'] / LIQUOR_BOTTLE_OZ
            results[inv_item]['items'].append(f"{item_name}: {qty} × {frozen_size}oz × {ZIPPARITA_TEQUILA_RATIO:.1%}")
            
            inv_item = 'LIQ Triple Sec'
            if inv_item not in results:
                results[inv_item] = {'oz': 0, 'bottles': 0, 'items': []}
            results[inv_item]['oz'] += triple_sec_oz
            results[inv_item]['bottles'] = results[inv_item]['oz'] / LIQUOR_BOTTLE_OZ
            results[inv_item]['items'].append(f"{item_name}: {qty} × {frozen_size}oz × {ZIPPARITA_TRIPLE_SEC_RATIO:.1%}")
            continue
        
        if is_frozen_marg:
            # Base frozen marg: tequila and triple sec from batch
            tequila_oz = qty * frozen_size * ZIPPARITA_TEQUILA_RATIO
            triple_sec_oz = qty * frozen_size * ZIPPARITA_TRIPLE_SEC_RATIO
            
            # Check for premium tequila variants
            tequila_item = 'TEQUILA Well'
            for pattern, premium_tequila in PREMIUM_TEQUILA_FLAVORS.items():
                if pattern.lower() in item_name.lower():
                    tequila_item = premium_tequila
                    break
            
            # Add tequila
            if tequila_item not in results:
                results[tequila_item] = {'oz': 0, 'bottles': 0, 'items': []}
            results[tequila_item]['oz'] += tequila_oz
            results[tequila_item]['bottles'] = results[tequila_item]['oz'] / LIQUOR_BOTTLE_OZ
            results[tequila_item]['items'].append(f"{item_name}: {qty} × {frozen_size}oz × {ZIPPARITA_TEQUILA_RATIO:.1%}")
            
            # Add triple sec
            inv_item = 'LIQ Triple Sec'
            if inv_item not in results:
                results[inv_item] = {'oz': 0, 'bottles': 0, 'items': []}
            results[inv_item]['oz'] += triple_sec_oz
            results[inv_item]['bottles'] = results[inv_item]['oz'] / LIQUOR_BOTTLE_OZ
            results[inv_item]['items'].append(f"{item_name}: {qty} × {frozen_size}oz × {ZIPPARITA_TRIPLE_SEC_RATIO:.1%}")

            # Check for flavor additions
            # Remove size suffixes to get the base flavor name
            flavor_clean = re.sub(r'\s*(16oz TO GO|24oz TO GO|BIG RITA)\s*$', '', clean_name).strip()
            
            for flavor_pattern, additions in MARGARITA_FLAVOR_ADDITIONS.items():
                if flavor_pattern.lower() in flavor_clean.lower():
                    flavor_multiplier = frozen_size / 10.0
                    
                    for add_inv_item, add_oz in additions.items():
                        total_flavor_oz = qty * add_oz * flavor_multiplier
                        
                        if add_inv_item not in results:
                            results[add_inv_item] = {'oz': 0, 'bottles': 0, 'items': []}
                        
                        results[add_inv_item]['oz'] += total_flavor_oz
                        
                        if 'BAR CONS' in add_inv_item or 'JUICE' in add_inv_item:
                            results[add_inv_item]['bottles'] = results[add_inv_item]['oz']
                        else:
                            results[add_inv_item]['bottles'] = results[add_inv_item]['oz'] / LIQUOR_BOTTLE_OZ
                        
                        results[add_inv_item]['items'].append(f"{item_name}: {qty} × {add_oz}oz (×{flavor_multiplier:.1f} size)")
                    break
            
            continue

        # Standard mixed drink recipes
        matched = False
        for recipe_name, ingredients in MIXED_DRINK_RECIPES.items():
            if recipe_name.lower() in clean_name.lower():
                for inv_item, oz_per_drink in ingredients.items():
                    if inv_item not in results:
                        results[inv_item] = {'oz': 0, 'bottles': 0, 'items': []}
                    results[inv_item]['oz'] += qty * oz_per_drink
                    if 'JUICE' in inv_item or 'BAR CONS' in inv_item:
                        results[inv_item]['bottles'] = results[inv_item]['oz']
                    else:
                        results[inv_item]['bottles'] = results[inv_item]['oz'] / LIQUOR_BOTTLE_OZ
                    results[inv_item]['items'].append(f"{item_name}: {qty} × {oz_per_drink}oz")
                matched = True
                break
        
        if not matched and qty > 0:
            unmatched.append(f"{item_name} (qty: {qty})")
    
    return results, unmatched


def aggregate_all_usage(sales_df, runtime_mappings=None):
    """
    Aggregate usage calculations from all categories.
    
    Returns:
        all_results: dict of {inv_item: {theoretical_usage, unit, details}}
        all_unmatched: list of unmatched items
    """
    all_results = {}
    all_unmatched = []

    # Draft beer
    draft_results, draft_unmatched = calculate_draft_beer_usage(sales_df, runtime_mappings)
    for inv_item, data in draft_results.items():
        all_results[inv_item] = {
            'theoretical_usage': round(data['kegs_used'], 2),
            'unit': 'kegs',
            'details': data['items']
        }
    all_unmatched.extend([f"[Draft] {item}" for item in draft_unmatched])

    # Bottle beer
    bottle_results, bottle_unmatched = calculate_bottle_beer_usage(sales_df, runtime_mappings)
    for inv_item, data in bottle_results.items():
        all_results[inv_item] = {
            'theoretical_usage': data['qty'],
            'unit': 'bottles/cans',
            'details': data['items']
        }
    all_unmatched.extend([f"[Bottle] {item}" for item in bottle_unmatched])

    # Liquor (straight pours)
    liquor_results, liquor_unmatched = calculate_liquor_usage(sales_df, runtime_mappings)
    for inv_item, data in liquor_results.items():
        if inv_item not in all_results:
            all_results[inv_item] = {
                'theoretical_usage': round(data['bottles'], 2),
                'unit': 'bottles',
                'oz': data['oz'],
                'details': data['items']
            }
        else:
            all_results[inv_item]['theoretical_usage'] += round(data['bottles'], 2)
            all_results[inv_item]['oz'] = all_results[inv_item].get('oz', 0) + data['oz']
            all_results[inv_item]['details'].extend(data['items'])
    all_unmatched.extend([f"[Liquor] {item}" for item in liquor_unmatched])

    # Mixed drinks
    mixed_results, mixed_unmatched = calculate_mixed_drink_usage(sales_df, runtime_mappings)
    for inv_item, data in mixed_results.items():
        if 'BEER BTL' in inv_item:
            if inv_item not in all_results:
                all_results[inv_item] = {
                    'theoretical_usage': data.get('qty', 0),
                    'unit': 'bottles/cans',
                    'details': data['items']
                }
            else:
                all_results[inv_item]['theoretical_usage'] += data.get('qty', 0)
                all_results[inv_item]['details'].extend(data['items'])
        elif 'JUICE' in inv_item or 'BAR CONS' in inv_item:
            if inv_item not in all_results:
                all_results[inv_item] = {
                    'theoretical_usage': round(data['oz'], 1),
                    'unit': 'oz',
                    'details': data['items']
                }
            else:
                all_results[inv_item]['theoretical_usage'] += round(data['oz'], 1)
                all_results[inv_item]['details'].extend(data['items'])
        else:
            if inv_item not in all_results:
                all_results[inv_item] = {
                    'theoretical_usage': round(data['bottles'], 2),
                    'unit': 'bottles',
                    'oz': data['oz'],
                    'details': data['items']
                }
            else:
                all_results[inv_item]['theoretical_usage'] += round(data['bottles'], 2)
                all_results[inv_item]['oz'] = all_results[inv_item].get('oz', 0) + data['oz']
                all_results[inv_item]['details'].extend(data['items'])
    all_unmatched.extend([f"[Mixed] {item}" for item in mixed_unmatched])
    
    # Wine
    wine_results, wine_unmatched = calculate_wine_usage(sales_df, runtime_mappings)
    for inv_item, data in wine_results.items():
        if inv_item not in all_results:
            all_results[inv_item] = {
                'theoretical_usage': round(data['bottles'], 2),
                'unit': 'bottles',
                'oz': data['oz'],
                'details': data['items']
            }
        else:
            all_results[inv_item]['theoretical_usage'] += round(data['bottles'], 2)
            all_results[inv_item]['oz'] = all_results[inv_item].get('oz', 0) + data['oz']
            all_results[inv_item]['details'].extend(data['items'])
    all_unmatched.extend([f"[Wine] {item}" for item in wine_unmatched])
    
    return all_results, all_unmatched
