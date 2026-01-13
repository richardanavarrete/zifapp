"""
Test script to verify the agent architecture works end-to-end.

This demonstrates how to use the new agent system without the Streamlit UI.
"""

import pandas as pd
from models import InventoryDataset, Item
from agent import run_agent
from datetime import datetime


def create_test_dataset():
    """Create a minimal test dataset."""
    # Create test items
    items = {
        "WHISKEY Buffalo Trace": Item(
            item_id="WHISKEY Buffalo Trace",
            display_name="WHISKEY Buffalo Trace",
            category="Unknown",
            vendor="Unknown"
        ),
        "BEER DFT Coors Light": Item(
            item_id="BEER DFT Coors Light",
            display_name="BEER DFT Coors Light",
            category="Unknown",
            vendor="Unknown"
        ),
    }

    # Create test records (4 weeks of data)
    records_data = []
    base_date = datetime(2024, 1, 1)

    for week in range(4):
        records_data.append({
            'item_id': 'WHISKEY Buffalo Trace',
            'week_date': pd.Timestamp(base_date) + pd.Timedelta(weeks=week),
            'on_hand': 12.0 - (week * 2),  # Decreasing inventory
            'usage': 2.0,
            'week_name': f'Week {week+1}',
            'source_file': 'test.xlsx'
        })

        records_data.append({
            'item_id': 'BEER DFT Coors Light',
            'week_date': pd.Timestamp(base_date) + pd.Timedelta(weeks=week),
            'on_hand': 8.0 - (week * 4),  # Rapidly decreasing
            'usage': 4.0,
            'week_name': f'Week {week+1}',
            'source_file': 'test.xlsx'
        })

    records_df = pd.DataFrame(records_data)

    return InventoryDataset(items=items, records=records_df)


def main():
    """Run a test agent execution."""
    print("=" * 60)
    print("AGENT ARCHITECTURE TEST")
    print("=" * 60)

    # Create test dataset
    print("\n1. Creating test dataset...")
    dataset = create_test_dataset()
    print(f"   ✓ Created dataset with {len(dataset.items)} items")
    print(f"   ✓ {len(dataset.records)} records")

    # Run agent
    print("\n2. Running agent...")
    result = run_agent(dataset, usage_column='avg_4wk')

    print(f"   ✓ Run ID: {result['run_id']}")
    print(f"   ✓ Summary: {result['summary']}")

    # Display recommendations
    print("\n3. Recommendations:")
    print("-" * 60)
    recs = result['recommendations']

    if not recs.empty:
        for _, row in recs.iterrows():
            print(f"\n   Item: {row['item_id']}")
            print(f"   Vendor: {row['vendor']} | Category: {row['category']}")
            print(f"   On Hand: {row['on_hand']:.2f} | Avg Usage: {row['avg_usage']:.2f}")
            print(f"   Weeks Left: {row['weeks_on_hand']:.1f} | Target: {row['target_weeks']:.1f}")
            print(f"   → Recommended Order: {row['recommended_qty']} units")
            print(f"   Confidence: {row['confidence']}")
            print(f"   Reason: {', '.join(row['reason_codes'])}")
            print(f"   Notes: {row['notes']}")
    else:
        print("   No recommendations generated")

    # Display items needing recount (now with detailed info)
    if result['items_needing_recount']:
        print("\n4. Items Needing Recount:")
        print("-" * 60)
        for item_info in result['items_needing_recount']:
            print(f"\n   ⚠️  {item_info['item_id']}")
            print(f"       Issue: {item_info.get('issue_type', 'Unknown')}")
            print(f"       {item_info.get('issue_description', '')}")
            if item_info.get('discrepancy'):
                print(f"       Discrepancy: {item_info['discrepancy']}")
            print(f"       On Hand: {item_info.get('on_hand', 'N/A')}")
            print(f"       Avg Usage: {item_info.get('avg_usage', 'N/A')}")

    # Display vendor keg info
    if result.get('vendor_keg_info'):
        print("\n4b. Vendor Keg Info (Crescent/Hensley):")
        print("-" * 60)
        for vendor, info in result['vendor_keg_info'].items():
            if info['total_kegs'] > 0:
                status = "✅ At discount" if info['at_discount_level'] else f"⚠️ Need {info['kegs_to_add']} more"
                print(f"   {vendor}: {info['total_kegs']} kegs ({status})")
                if not info['at_discount_level'] and info.get('adjustment_suggestions'):
                    print("   Suggestions:")
                    for sug in info['adjustment_suggestions']:
                        print(f"      - {sug['item_id']}: Add {sug['suggested_add']} ({sug['reason']})")

    # Display summary stats
    print("\n5. Summary Statistics:")
    print("-" * 60)
    for key, value in result['summary_stats'].items():
        print(f"   {key}: {value}")

    print("\n" + "=" * 60)
    print("✅ Agent test completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
