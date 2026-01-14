# Batch Inventory Counting Guide

## The Problem

When you make batched products like **Milagro Marg On Tap**, the ingredients are used upfront but sold gradually over time. This creates timing mismatches in variance analysis:

- **Week 1**: You make a batch using 7 bottles of Milagro Silver
  - Actual usage: 7 bottles (inventory decreases)
  - Sales/Theoretical usage: 0.5 bottles (only sold a few drinks)
  - Variance: HUGE negative variance (used way more than sold)

- **Week 2**: You sell from the pre-made batch
  - Actual usage: 0 bottles (no new tequila used)
  - Sales/Theoretical usage: 4.45 bottles (sold lots of drinks)
  - Variance: HUGE positive variance (sold way more than used)

## The Solution

**Track batch products as inventory items, and the system automatically converts them to ingredient equivalents.**

The system now automatically accounts for batch inventory:
1. Track "Milagro Marg On Tap" as a regular inventory item in your BEVWEEKLY spreadsheet
2. Count the remaining batch volume in liters during each inventory count
3. The variance analysis automatically converts batch volume to ingredient bottles
4. Your "true on-hand" inventory includes both physical bottles AND the ingredients in batches

### How It Works

1. **Add "Milagro Marg On Tap" to your BEVWEEKLY spreadsheet** as a new inventory item
   - Unit of Measure: Liters
   - Category: Bar Consumables (or create new category)

2. **During each inventory count**, measure remaining batch volume in liters
   - Example: 5 liters of Milagro Marg On Tap remaining
   - **Enter 5L in the "End Inventory" column** for Milagro Marg On Tap

3. **The variance analysis automatically converts** batch to ingredients:
   - Physical Milagro Silver: 2 bottles (from your inventory)
   - Batch equivalent: 1.25 bottles (automatically calculated from 5L batch)
   - **True on-hand displayed: 3.25 bottles** (no manual calculation needed!)

4. **Variance is calculated** against the true on-hand amount

### Why This Works

The batch ingredients are calculated using your actual batch recipe:
- **Milagro Marg On Tap batch** (12L total):
  - 3 bottles (3L) Milagro Silver = **25%** of batch
  - 2 bottles (2L) Triple Sec = **16.7%** of batch
  - ~7L frozen mix (the rest)

When you count the batch and convert it back, you're accounting for the tequila and triple sec that's already mixed but still in your possession.

## Setting Up Batch Tracking

### Step 1: Add to BEVWEEKLY Spreadsheet

Add a new row to your inventory spreadsheet:
- **Item**: Milagro Marg On Tap
- **Unit of Measure**: Liters
- **Unit Cost**: (calculate based on ingredient costs, or use $0 for now)
- **Beginning Inventory, Purchases, Ending Inventory**: Track in liters

### Step 2: Count During Inventory

When doing inventory counts:
1. Measure remaining batch volume in liters (use consistent container/method)
2. Enter the volume in the "End Inventory" column for Milagro Marg On Tap
3. Count physical Milagro Silver and Triple Sec bottles normally
4. The system handles the rest automatically!

### Example

**Week 1 Inventory:**
- Milagro Marg On Tap: 3.5L remaining → Enter **3.5** in End Inventory
- TEQUILA Milagro Silver: 2 bottles on shelf → Enter **2** in End Inventory
- LIQ Triple Sec: 1 bottle on shelf → Enter **1** in End Inventory

**Variance Analysis (automatic):**
- Milagro Silver physical: 2 bottles
- Milagro Silver in batch: 0.88 bottles (auto-calculated from 3.5L)
- **True on-hand: 2.88 bottles** (shown in variance report)
- Variance calculated against 2.88, not 2!

## Tips

- **Measure consistently**: Use the same container/method each week for accurate volume measurement
- **Check batch levels weekly**: Don't wait until variance alerts—make this part of your regular inventory process
- **Track batch production**: Note when you make new batches so you can anticipate high usage weeks
- **Multiple batches**: If you have multiple batches at different stages, measure and convert each one

## Expected Results

After implementing batch counting:
- **Variance should drop significantly** (from 300%+ to <50%)
- **Week-to-week variance will still fluctuate** (batch production weeks vs selling weeks)
- **Multi-week average variance should be minimal** (within normal spillage/waste range)

## Technical Details

The batch converter uses these ratios from your actual recipe:

```python
# From config/constants.py
ZIPPARITA_BATCH_TOTAL_OZ = 405.8  # 12L
ZIPPARITA_TEQUILA_OZ = 101.4      # 3 bottles
ZIPPARITA_TRIPLE_SEC_OZ = 67.6    # 2 bottles
LIQUOR_BOTTLE_OZ = 33.8           # 1L bottles

ZIPPARITA_TEQUILA_RATIO = 0.25    # 25%
ZIPPARITA_TRIPLE_SEC_RATIO = 0.167 # 16.7%
```

If your recipe changes, update these constants in the config file.
