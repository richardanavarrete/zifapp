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

**Count batch products and convert them back to ingredient bottles when doing inventory.**

The tequila in your Milagro Marg On Tap batch is still "in house"—it's just already mixed. By counting it and adding the equivalent bottles to your inventory count, the variance evens out.

### How It Works

1. **During inventory count**, measure your remaining batch volume
   - Example: 5 liters (169oz) of Milagro Marg On Tap remaining

2. **Use the Batch Converter** (in the app sidebar) to convert to ingredient bottles:
   - 5L batch = **1.25 bottles** of Milagro Silver + **0.83 bottles** of Triple Sec

3. **Add these to your physical inventory**:
   - Physical bottles on shelf: 2 bottles
   - Batch equivalent: 1.25 bottles
   - **Total inventory to record: 3.25 bottles**

4. **Enter the total** (3.25) in your inventory spreadsheet as the ending inventory

### Why This Works

The batch ingredients are calculated using your actual batch recipe:
- **Milagro Marg On Tap batch** (12L total):
  - 3 bottles (3L) Milagro Silver = **25%** of batch
  - 2 bottles (2L) Triple Sec = **16.7%** of batch
  - ~7L frozen mix (the rest)

When you count the batch and convert it back, you're accounting for the tequila and triple sec that's already mixed but still in your possession.

## Using the Batch Converter

### In the App

1. Open the Bev Usage Analyzer
2. Look for **"🧪 Batch Converter"** in the left sidebar
3. Expand **"Milagro Marg On Tap"**
4. Choose your measurement unit (Liters or Ounces)
5. Enter the remaining batch volume
6. The app shows you exactly how many bottles to add

### Example Calculation

**Scenario**: You have 3.5L of Milagro Marg On Tap remaining

**Conversion**:
- 3.5L = 118.3oz
- Milagro Silver: 118.3oz × 25% = 29.6oz = **0.88 bottles**
- Triple Sec: 118.3oz × 16.7% = 19.8oz = **0.59 bottles**

**Inventory Count**:
- Milagro Silver physical: 2 bottles
- Milagro Silver batch: 0.88 bottles
- **Total Milagro Silver: 2.88 bottles** ← Enter this in spreadsheet

- Triple Sec physical: 1 bottle
- Triple Sec batch: 0.59 bottles
- **Total Triple Sec: 1.59 bottles** ← Enter this in spreadsheet

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
