import pandas as pd
import re
import sys
import os

# --- PRO FIX: Add Project Root to Path ---
# This ensures Python can find the 'config' folder even from inside 'utils'
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# -----------------------------------------

# Now import specific submodules (Explicit is better than implicit)
from config.constants import (
    COUNT_OZ, STANDARD_POUR_OZ, HALF_BARREL_OZ, LIQUOR_BOTTLE_OZ, KEG_50L_OZ,
    DRAFT_POUR_SIZES, ZIPPARITA_TEQUILA_RATIO, ZIPPARITA_TRIPLE_SEC_RATIO,
    WINE_GLASS_OZ, WINE_BOTTLE_OZ, KEG_50L_OZ, LIQUOR_BOTTLE_750_OZ, WINE_BOTTLE_MAGNUM_OZ
)
from config.draft_beer_map import DRAFT_BEER_MAP, DRAFT_SKIP_ITEMS
from config.bottle_beer_map import BOTTLE_BEER_MAP
from config.liquor_map import LIQUOR_MAP
from config.wine_map import WINE_MAP
from config.mixed_drinks import MIXED_DRINK_RECIPES
from config.margarita_flavors import MARGARITA_FLAVOR_ADDITIONS, PREMIUM_TEQUILA_FLAVORS
from config.bar_consumables import BAR_CONSUMABLES_MAP
from config.manual_overrides import MANUAL_MAPPINGS, ENABLE_MANUAL_MAPPINGS

def parse_sales_mix_csv(uploaded_csv):
    """
    Parse the GEMpos Sales Mix CSV into a structured DataFrame.
    
    Returns DataFrame with columns: Category, Subcategory, Item, Qty, Amount
    """
    # Read the CSV
    df = pd.read_csv(uploaded_csv, header=None)
    
    # Find the header row (contains "Item ID", "Qty", "Amount")
    header_row_idx = None
    for idx, row in df.iterrows():
        row_str = ','.join(row.astype(str))
        if 'Item ID' in row_str and 'Qty' in row_str:
            header_row_idx = idx
            break
    
    if header_row_idx is None:
        raise ValueError("Could not find header row in CSV")
    
    # Get column positions
    header_row = df.iloc[header_row_idx]
    qty_col = None
    amount_col = None
    
    for i, val in enumerate(header_row):
        if str(val).strip() == 'Qty':
            qty_col = i
        elif str(val).strip() == 'Amount':
            amount_col = i
    
    if qty_col is None:
        raise ValueError("Could not find 'Qty' column")
    
    # Parse the data rows
    parsed_items = []
    current_category = None
    current_subcategory = None
    
    for idx in range(header_row_idx + 1, len(df)):
        row = df.iloc[idx]
        
        # Skip empty rows and grand total
        row_str = ','.join(row.astype(str).fillna(''))
        if 'Grand Total' in row_str:
            break
        
        # Check for category markers [+] (e.g., "[+],Bottle,..." or "[+],Liquor,...")
        # The [+] is in column 0, category name in column 1
        if str(row.iloc[0]).strip() == '[+]':
            current_category = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else None
            current_subcategory = None
            continue
        
        # Check for subcategory markers (e.g., ",,[+],Mixed Drinks,...")
        # The [+] is in column 2, subcategory name in column 3
        if len(row) > 3 and str(row.iloc[2]).strip() == '[+]':
            current_subcategory = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else None
            continue
        
        # Find the item name (usually in columns 2-6)
        item_name = None
        for col_idx in range(2, 7):
            if col_idx < len(row) and pd.notna(row.iloc[col_idx]) and str(row.iloc[col_idx]).strip():
                item_name = str(row.iloc[col_idx]).strip()
                break
        
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
        amount = 0
        if amount_col and amount_col < len(row) and pd.notna(row.iloc[amount_col]):
            try:
                amt_str = str(row.iloc[amount_col]).replace('$', '').replace(',', '')
                amount = float(amt_str)
            except (ValueError, TypeError):
                amount = 0
       
        
        if qty > 0:
            parsed_items.append({
                'Category': current_category,
                'Subcategory': current_subcategory,
                'Item': item_name,
                'Qty': qty,
                'Amount': amount,
            })
    
    return pd.DataFrame(parsed_items)


def calculate_draft_beer_usage(sales_df, runtime_mappings=None):
    """Calculate theoretical keg usage from draft beer sales."""
    results = {}
    unmatched = []

    # Merge runtime mappings with config mappings
    all_manual_mappings = dict(MANUAL_MAPPINGS)
    if runtime_mappings:
        all_manual_mappings.update(runtime_mappings)

    draft_sales = sales_df[sales_df['Category'] == 'Draft'].copy()

    for _, row in draft_sales.iterrows():
        item_name = row['Item']
        qty = row['Qty']

        # Check manual overrides first (exact match, takes precedence)
        if ENABLE_MANUAL_MAPPINGS and item_name in all_manual_mappings:
            for inv_item, oz_per_item in all_manual_mappings[item_name].items():
                if inv_item not in results:
                    results[inv_item] = {
                        'total_oz': 0,
                        'keg_size': HALF_BARREL_OZ,  # default
                        'kegs_used': 0,
                        'items': []
                    }
                oz_used = qty * oz_per_item
                results[inv_item]['total_oz'] += oz_used
                results[inv_item]['kegs_used'] = results[inv_item]['total_oz'] / results[inv_item]['keg_size']
                results[inv_item]['items'].append(f"{item_name}: {qty} × {oz_per_item}oz [MANUAL]")
            # Manual mapping found, skip all other matching
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
                kegs_used = total_oz / keg_size

                if inv_item not in results:
                    results[inv_item] = {
                        'total_oz': 0,
                        'keg_size': keg_size,
                        'kegs_used': 0,
                        'items': []
                    }
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

    # Merge runtime mappings with config mappings
    all_manual_mappings = dict(MANUAL_MAPPINGS)
    if runtime_mappings:
        all_manual_mappings.update(runtime_mappings)

    bottle_sales = sales_df[sales_df['Category'] == 'Bottle'].copy()

    for _, row in bottle_sales.iterrows():
        item_name = row['Item']
        qty = row['Qty']

        # Check manual overrides first (exact match, takes precedence)
        if ENABLE_MANUAL_MAPPINGS and item_name in all_manual_mappings:
            for inv_item, count_per_item in all_manual_mappings[item_name].items():
                if inv_item not in results:
                    results[inv_item] = {'qty': 0, 'items': []}
                results[inv_item]['qty'] += qty * count_per_item
                results[inv_item]['items'].append(f"{item_name}: {qty} × {count_per_item} [MANUAL]")
            # Manual mapping found, skip all other matching
            continue

        # Clean up item name for matching (remove (FS) suffix)
        clean_name = re.sub(r'\s*\(FS\)\s*$', '', item_name).strip()

        # Find matching inventory item
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

    # Merge runtime mappings with config mappings
    all_manual_mappings = dict(MANUAL_MAPPINGS)
    if runtime_mappings:
        all_manual_mappings.update(runtime_mappings)

    # Process Liquor category (straight pours)
    liquor_sales = sales_df[sales_df['Category'] == 'Liquor'].copy()

    for _, row in liquor_sales.iterrows():
        item_name = row['Item']
        qty = row['Qty']

        # Check manual overrides first (exact match, takes precedence)
        if ENABLE_MANUAL_MAPPINGS and item_name in all_manual_mappings:
            for inv_item, oz_per_drink in all_manual_mappings[item_name].items():
                if inv_item not in results:
                    results[inv_item] = {'oz': 0, 'bottles': 0, 'items': []}
                results[inv_item]['oz'] += qty * oz_per_drink
                results[inv_item]['bottles'] = results[inv_item]['oz'] / LIQUOR_BOTTLE_OZ
                results[inv_item]['items'].append(f"{item_name}: {qty} × {oz_per_drink}oz [MANUAL]")
            # Manual mapping found, skip all other matching
            continue

        # Clean up item name
        clean_name = re.sub(r'\s*\(FS\)\s*$', '', item_name).strip()
        is_bump = '(Flavor)', '(Bump)' in item_name
        clean_name = re.sub(r'\s*\(Bump\)\s*$', '', clean_name).strip()

        # Determine pour size
        pour_oz = COUNT_OZ if is_bump else STANDARD_POUR_OZ

        # Find matching inventory item
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

    # Merge runtime mappings with config mappings
    all_manual_mappings = dict(MANUAL_MAPPINGS)
    if runtime_mappings:
        all_manual_mappings.update(runtime_mappings)

    wine_sales = sales_df[sales_df['Category'] == 'Wine'].copy()

    for _, row in wine_sales.iterrows():
        item_name = row['Item']
        qty = row['Qty']

        # Check manual overrides first (exact match, takes precedence)
        if ENABLE_MANUAL_MAPPINGS and item_name in all_manual_mappings:
            for inv_item, oz_per_drink in all_manual_mappings[item_name].items():
                if inv_item not in results:
                    results[inv_item] = {'oz': 0, 'bottles': 0, 'items': []}
                results[inv_item]['oz'] += qty * oz_per_drink
                results[inv_item]['bottles'] = results[inv_item]['oz'] / WINE_BOTTLE_OZ
                results[inv_item]['items'].append(f"{item_name}: {qty} × {oz_per_drink}oz [MANUAL]")
            # Manual mapping found, skip all other matching
            continue

        # Determine if it's a glass or bottle
        is_bottle = 'BTL' in item_name.upper() or 'Bottle' in item_name
        pour_oz = WINE_BOTTLE_OZ if is_bottle else WINE_GLASS_OZ

        # Find matching inventory item
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
    """Calculate theoretical usage from mixed drinks including frozen margaritas.

    Args:
        sales_df: DataFrame with sales data
        runtime_mappings: Optional dict of runtime manual mappings to merge with config
    """
    results = {}
    unmatched = []

    # Merge runtime mappings with config mappings
    all_manual_mappings = dict(MANUAL_MAPPINGS)
    if runtime_mappings:
        all_manual_mappings.update(runtime_mappings)

    mixed_sales = sales_df[sales_df['Subcategory'] == 'Mixed Drinks'].copy()

    for _, row in mixed_sales.iterrows():
        item_name = row['Item']
        qty = row['Qty']

        # Check manual overrides first (exact match, takes precedence)
        if ENABLE_MANUAL_MAPPINGS and item_name in all_manual_mappings:
            for inv_item, oz_per_drink in all_manual_mappings[item_name].items():
                if inv_item not in results:
                    results[inv_item] = {'oz': 0, 'bottles': 0, 'items': []}
                results[inv_item]['oz'] += qty * oz_per_drink
                # Use appropriate conversion
                if 'JUICE' in inv_item or 'BAR CONS' in inv_item:
                    results[inv_item]['bottles'] = results[inv_item]['oz']  # Track in oz
                else:
                    results[inv_item]['bottles'] = results[inv_item]['oz'] / LIQUOR_BOTTLE_OZ
                results[inv_item]['items'].append(f"{item_name}: {qty} × {oz_per_drink}oz [MANUAL]")
            # Manual mapping found, skip all other matching
            continue

        # Clean up item name for matching
        clean_name = re.sub(r'\s*\(FS\)\s*$', '', item_name).strip()
        clean_name = re.sub(r'\s*16oz TO GO\s*$', '', clean_name).strip()
        clean_name = re.sub(r'\s*24oz TO GO\s*$', '', clean_name).strip()
        clean_name = re.sub(r'\s*BIG RITA\s*$', '', clean_name).strip()
        
        # Determine if it's a frozen margarita variant
        is_frozen_marg = False
        frozen_size = 10  # default Zipparita size
        
        # Check for frozen marg indicators
        if clean_name == 'Zipparita':
            is_frozen_marg = True
            frozen_size = 10
        elif clean_name == 'BIG Zipparita':
            is_frozen_marg = True
            frozen_size = 16
        elif item_name == 'TO GO RITA 16oz':
            is_frozen_marg = True
            frozen_size = 16
        elif item_name == 'TO GO RITA 24oz':
            is_frozen_marg = True
            frozen_size = 24
        elif 'Flavor' in item_name:
            is_frozen_marg = True
            # Determine size based on item name
            if '24oz' in item_name:
                frozen_size = 24
            elif '16oz' in item_name or 'BIG' in item_name:
                frozen_size = 16
            else:
                frozen_size = 10
        elif 'Milagro Marg On Tap' in item_name:
            # Special handling for Milagro on tap
            is_frozen_marg = True
            frozen_size = 5  # Assume standard size
            
            tequila_oz = qty * frozen_size * ZIPPARITA_TEQUILA_RATIO
            triple_sec_oz = qty * frozen_size * ZIPPARITA_TRIPLE_SEC_RATIO
            
            # Uses Milagro Silver instead of well
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
            # Calculate base frozen marg usage (tequila and triple sec from batch)
            tequila_oz = qty * frozen_size * ZIPPARITA_TEQUILA_RATIO
            triple_sec_oz = qty * frozen_size * ZIPPARITA_TRIPLE_SEC_RATIO
            
            # Check for premium tequila variants
            tequila_item = 'TEQUILA Well'
            for pattern, premium_tequila in PREMIUM_TEQUILA_FLAVORS.items():
                if pattern.lower() in item_name.lower():
                    tequila_item = premium_tequila
                    break
            
            # Add tequila usage
            if tequila_item not in results:
                results[tequila_item] = {'oz': 0, 'bottles': 0, 'items': []}
            results[tequila_item]['oz'] += tequila_oz
            results[tequila_item]['bottles'] = results[tequila_item]['oz'] / LIQUOR_BOTTLE_OZ
            results[tequila_item]['items'].append(f"{item_name}: {qty} × {frozen_size}oz × {ZIPPARITA_TEQUILA_RATIO:.1%}")
            
            # Add triple sec usage
            inv_item = 'LIQ Triple Sec'
            if inv_item not in results:
                results[inv_item] = {'oz': 0, 'bottles': 0, 'items': []}
            results[inv_item]['oz'] += triple_sec_oz
            results[inv_item]['bottles'] = results[inv_item]['oz'] / LIQUOR_BOTTLE_OZ
            results[inv_item]['items'].append(f"{item_name}: {qty} × {frozen_size}oz × {ZIPPARITA_TRIPLE_SEC_RATIO:.1%}")

            # Check for flavor additions
            for flavor_pattern, additions in MARGARITA_FLAVOR_ADDITIONS.items():
                if flavor_pattern.lower() in clean_name.lower():
                    # We found a flavor! (e.g. "Mango Flavor")

                    # Determine multiplier based on size
                    # (You already set frozen_size above, so just use that ratio)
                    # Standard flavor dose is for a 10oz drink.
                    # If drink is 16oz, we need 1.6x the flavor.
                    flavor_multiplier = frozen_size / 10.0

                    for add_inv_item, add_oz in additions.items():
                        total_flavor_oz = qty * add_oz * flavor_multiplier

                        if add_inv_item not in results:
                            results[add_inv_item] = {'oz': 0, 'bottles': 0, 'items': []}

                        results[add_inv_item]['oz'] += total_flavor_oz

                        # Handle units (Bottles vs Puree/Consumables)
                        if 'BAR CONS' in add_inv_item or 'JUICE' in add_inv_item:
                             # Keep consumables in oz (don't divide by bottle size)
                             # We'll set 'bottles' to match 'oz' for now so it doesn't crash,
                             # but the aggregator handles unit types later.
                             results[add_inv_item]['bottles'] = results[add_inv_item]['oz']
                        else:
                            results[add_inv_item]['bottles'] = results[add_inv_item]['oz'] / LIQUOR_BOTTLE_OZ

                        results[add_inv_item]['items'].append(f"{item_name}: {qty} x {add_oz}oz (x{flavor_multiplier} size)")

                    # Stop looking for other flavors once we found the right one
                    break

            # Frozen marg processed, skip standard mixed drink matching
            continue

        # Check for standard mixed drink recipes
        matched = False
        for recipe_name, ingredients in MIXED_DRINK_RECIPES.items():
            if recipe_name.lower() in clean_name.lower():
                for inv_item, oz_per_drink in ingredients.items():
                    if inv_item not in results:
                        results[inv_item] = {'oz': 0, 'bottles': 0, 'items': []}
                    results[inv_item]['oz'] += qty * oz_per_drink
                    # Use appropriate conversion
                    if 'JUICE' in inv_item or 'BAR CONS' in inv_item:
                        results[inv_item]['bottles'] = results[inv_item]['oz']  # Track in oz
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

    Args:
        sales_df: DataFrame with sales data
        runtime_mappings: Optional dict of runtime manual mappings

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
            # Handle coronitas from Zippa Rona
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
            # Track consumables in oz
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
