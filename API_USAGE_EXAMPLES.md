# API Usage Examples

This document demonstrates how both **humans** and **agents** can use the Inventory Management API.

## Table of Contents

1. [Starting the API Server](#starting-the-api-server)
2. [Human Usage Examples](#human-usage-examples)
3. [Agent Usage Examples](#agent-usage-examples)
4. [Direct HTTP Examples](#direct-http-examples)
5. [Integration Patterns](#integration-patterns)

---

## Starting the API Server

```bash
# Start the API server
python api_comprehensive.py

# Or with custom host/port
uvicorn api_comprehensive:app --host 0.0.0.0 --port 8000 --reload
```

**Interactive Documentation:**
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Human Usage Examples

### Example 1: Weekly Inventory Review

```python
from api_client import InventoryClient

# Initialize client
client = InventoryClient("http://localhost:8000")

# Upload this week's inventory files
dataset_id = client.upload_files([
    "BEVWEEKLY_Jan_Week1.xlsx",
    "BEVWEEKLY_Jan_Week2.xlsx",
    "BEVWEEKLY_Jan_Week3.xlsx"
])

print(f"Dataset ID: {dataset_id}")

# Get summary analytics
summary = client.get_summary(dataset_id)

# Filter by vendor
breakthru_items = client.get_summary(dataset_id, vendor="Breakthru")
print(f"Breakthru has {len(breakthru_items)} items")

# View trends
trends = client.get_trends(dataset_id)
print(f"Items trending up: {len(trends['trending_up'])}")
print(f"Low stock items: {len(trends['low_stock'])}")

# Get vendor summaries
vendors = client.get_vendor_summary(dataset_id)
for vendor in vendors:
    print(f"{vendor['vendor']}: {vendor['total_items']} items, "
          f"{vendor['items_low_stock']} low stock")
```

### Example 2: Generating Draft Orders

```python
from api_client import InventoryClient

client = InventoryClient("http://localhost:8000")

# Upload data
dataset_id = client.upload_files(["current_week.xlsx"])

# Run the agent to get recommendations
result = client.run_agent(
    dataset_id,
    usage_column='avg_4wk',  # Use 4-week average
    custom_targets={
        'Whiskey': 5.0,  # Keep 5 weeks of whiskey
        'Draft Beer': 1.5  # Keep 1.5 weeks of draft beer
    }
)

print(f"Run ID: {result['run_id']}")
print(f"Summary: {result['summary']}")

# Get recommendations for a specific vendor
breakthru_order = client.get_recommendations(
    result['run_id'],
    vendor="Breakthru",
    items_to_order_only=True
)

print(f"\nBreakthru Order:")
for item in breakthru_order:
    print(f"  {item['item_id']}: {item['recommended_qty']} units "
          f"({item['confidence']} confidence)")
    if item['notes']:
        print(f"    Note: {item['notes']}")

# Download order as CSV
csv_file = client.download_order(
    result['run_id'],
    vendor="Breakthru",
    save_path="breakthru_order.csv"
)
print(f"\nOrder saved to: {csv_file}")
```

### Example 3: Item Deep Dive

```python
from api_client import InventoryClient

client = InventoryClient("http://localhost:8000")
dataset_id = "your-dataset-id"

# Get detailed analytics for a specific item
item_details = client.get_item_details(dataset_id, "WHISKEY Buffalo Trace")

print(f"Item: {item_details['item']['display_name']}")
print(f"Vendor: {item_details['item']['vendor']}")
print(f"Category: {item_details['item']['category']}")
print(f"\nCurrent Stats:")
print(f"  On Hand: {item_details['features']['on_hand']}")
print(f"  Avg Usage (4wk): {item_details['features']['avg_4wk']}")
print(f"  Weeks Remaining: {item_details['features']['weeks_on_hand_4wk']}")
print(f"  Trend: {item_details['features']['trend']}")

# Get chart data for visualization
chart_data = client.get_item_chart(dataset_id, "WHISKEY Buffalo Trace")

# Plot with matplotlib/plotly
import matplotlib.pyplot as plt
plt.plot(chart_data['dates'], chart_data['usage'], label='Usage')
plt.plot(chart_data['dates'], chart_data['on_hand'], label='On Hand')
plt.xlabel('Date')
plt.ylabel('Units')
plt.title('WHISKEY Buffalo Trace - Usage History')
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('buffalo_trace_history.png')
```

### Example 4: Setting Preferences

```python
from api_client import InventoryClient

client = InventoryClient("http://localhost:8000")

# Set custom target for a specific item
client.set_preference(
    "WHISKEY Buffalo Trace",
    target_weeks_override=6.0,  # Always keep 6 weeks
    notes="High demand item, keep extra stock"
)

# Mark an item as never order (discontinued)
client.set_preference(
    "VODKA Old Brand",
    never_order=True,
    notes="Discontinued by vendor"
)

# View all preferences
prefs = client.get_preferences()
print(f"Total preferences set: {len(prefs)}")
```

### Example 5: Tracking Order History

```python
from api_client import InventoryClient

client = InventoryClient("http://localhost:8000")

# Get recent agent runs
runs = client.get_agent_runs(limit=5)

for run in runs:
    print(f"\nRun {run['run_id']} - {run['timestamp']}")
    print(f"  Items to order: {run['items_to_order']}")
    print(f"  Total qty: {run['total_qty_recommended']}")

# Get history for a specific item
item_history = client.get_item_history("WHISKEY Buffalo Trace", limit=10)

print("\nRecommendation History:")
for rec in item_history['recommendations']:
    print(f"  {rec['timestamp']}: Recommended {rec['recommended_qty']} units "
          f"(confidence: {rec['confidence']})")

print("\nAction History:")
for action in item_history['actions']:
    print(f"  {action['timestamp']}: Ordered {action['approved_qty']} units")
```

---

## Agent Usage Examples

### Example 1: Autonomous Weekly Analysis

```python
from api_client import AgentClient

# Initialize agent client
agent = AgentClient("http://localhost:8000")

# Ingest new data
dataset_id = agent.ingest_data(["current_week.xlsx"])

# Analyze inventory state
analysis = agent.analyze_inventory(dataset_id)

print("Inventory Analysis:")
print(f"  Total items: {len(analysis['summary'])}")
print(f"  Items trending up: {len(analysis['trending_up'])}")
print(f"  Items trending down: {len(analysis['trending_down'])}")
print(f"  Low stock items: {len(analysis['low_stock'])}")

# Make decisions
decisions = agent.make_decisions(dataset_id, usage_metric='avg_4wk')

print(f"\nDecision Run ID: {decisions['run_id']}")
print(f"Summary: {decisions['summary']}")

# Inspect items needing attention
if decisions['stats']['stockout_risks'] > 0:
    print(f"\n⚠️  {decisions['stats']['stockout_risks']} items at stockout risk!")

    # Get detailed recommendations
    recs = agent.get_decision_details(decisions['run_id'])

    for rec in recs:
        if 'STOCKOUT_RISK' in rec['reason_codes']:
            print(f"  - {rec['item_id']}: {rec['weeks_on_hand']:.1f} weeks left")
```

### Example 2: Agent Learning Loop

```python
from api_client import AgentClient

agent = AgentClient("http://localhost:8000")

# Make decisions
dataset_id = agent.ingest_data(["current_week.xlsx"])
decisions = agent.make_decisions(dataset_id)

# Get recommendations
recommendations = agent.get_decision_details(decisions['run_id'])

# Simulate human review (in real system, human would approve via UI)
approved_items = []
for rec in recommendations:
    if rec['recommended_qty'] > 0 and rec['confidence'] == 'high':
        approved_items.append({
            'item_id': rec['item_id'],
            'recommended_qty': rec['recommended_qty'],
            'approved_qty': rec['recommended_qty'],  # Could be modified by human
            'user_override_reason': ''
        })

# Submit approved orders
agent.submit_order(decisions['run_id'], approved_items)

# Learn from patterns
# If user consistently overrides agent's recommendations, store that knowledge
for rec in recommendations:
    if rec['confidence'] == 'low':
        # Agent learns to be more conservative with this item
        agent.learn_from_feedback(rec['item_id'], {
            'notes': 'Auto-learned: High override rate, increase caution'
        })
```

### Example 3: Deep Item Inspection

```python
from api_client import AgentClient

agent = AgentClient("http://localhost:8000")
dataset_id = "your-dataset-id"

# Inspect a specific item in detail
inspection = agent.inspect_item(dataset_id, "WHISKEY Buffalo Trace")

print("Current State:")
print(f"  On Hand: {inspection['current_state']['on_hand']}")
print(f"  Avg Usage: {inspection['current_state']['avg_4wk']}")
print(f"  Trend: {inspection['current_state']['trend']}")
print(f"  Volatility: {inspection['current_state']['volatility']}")

print("\nMetadata:")
print(f"  Vendor: {inspection['metadata']['vendor']}")
print(f"  Category: {inspection['metadata']['category']}")

print("\nWeekly History:")
for week in inspection['weekly_history'][-4:]:  # Last 4 weeks
    print(f"  {week['week_name']}: Usage={week['usage']}, OnHand={week['on_hand']}")

print("\nDecision History:")
for decision in inspection['decision_history'][:3]:  # Last 3 decisions
    print(f"  {decision['timestamp']}: Recommended {decision['recommended_qty']}")

# Agent can use this to make more informed decisions
if inspection['current_state']['volatility'] > 1.0:
    print("\n⚠️  High volatility detected - recommend cautious ordering")
```

### Example 4: Knowledge Base Management

```python
from api_client import AgentClient

agent = AgentClient("http://localhost:8000")

# Retrieve learned preferences
knowledge = agent.get_knowledge_base()

print("Agent Knowledge Base:")
for item_id, prefs in knowledge['preferences'].items():
    if prefs['never_order']:
        print(f"  {item_id}: NEVER ORDER")
    elif prefs['target_weeks_override']:
        print(f"  {item_id}: Custom target {prefs['target_weeks_override']} weeks")

# Agent can use this knowledge in decision-making
# (Already automatically applied by the API)
```

### Example 5: Comparative Analysis

```python
from api_client import AgentClient

agent = AgentClient("http://localhost:8000")

# Get historical decision performance
history = agent.get_decision_history(limit=20)

# Analyze how decisions changed over time
print("Decision History Analysis:")
for run in history:
    print(f"{run['timestamp']}: {run['items_to_order']} items, "
          f"{run['total_qty_recommended']} units")

# Agent can analyze trends in its own decision-making
# e.g., "Am I ordering more or less over time?"
# "Which categories am I consistently over/under-ordering?"
```

---

## Direct HTTP Examples

### Using cURL

```bash
# Upload data
curl -X POST "http://localhost:8000/upload" \
  -F "files=@week1.xlsx" \
  -F "files=@week2.xlsx"

# Get summary
curl "http://localhost:8000/analytics/{dataset_id}/summary"

# Run agent
curl -X POST "http://localhost:8000/agent/run/{dataset_id}" \
  -H "Content-Type: application/json" \
  -d '{"usage_column": "avg_4wk", "smoothing_level": 0.3}'

# Get recommendations
curl "http://localhost:8000/agent/runs/{run_id}/recommendations?items_to_order_only=true"

# Export order
curl "http://localhost:8000/agent/runs/{run_id}/export?vendor=Breakthru" \
  -o breakthru_order.csv
```

### Using requests library

```python
import requests

base_url = "http://localhost:8000"

# Upload files
with open("week1.xlsx", "rb") as f:
    files = {"files": ("week1.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    response = requests.post(f"{base_url}/upload", files=files)
    dataset_id = response.json()['dataset_id']

# Run agent
response = requests.post(
    f"{base_url}/agent/run/{dataset_id}",
    json={
        "usage_column": "avg_4wk",
        "smoothing_level": 0.3,
        "trend_threshold": 0.1
    }
)
result = response.json()
run_id = result['run_id']

# Get recommendations
response = requests.get(
    f"{base_url}/agent/runs/{run_id}/recommendations",
    params={"items_to_order_only": True}
)
recommendations = response.json()['recommendations']

print(f"Got {len(recommendations)} recommendations")
```

---

## Integration Patterns

### Pattern 1: Streamlit Frontend → API Backend

```python
# In your Streamlit app
import streamlit as st
from api_client import InventoryClient

client = InventoryClient("http://localhost:8000")

# File upload
uploaded_files = st.file_uploader("Upload Excel files", accept_multiple_files=True)

if uploaded_files:
    # Save temp files and upload
    temp_paths = []
    for file in uploaded_files:
        temp_path = f"/tmp/{file.name}"
        with open(temp_path, "wb") as f:
            f.write(file.read())
        temp_paths.append(temp_path)

    dataset_id = client.upload_files(temp_paths)
    st.success(f"Dataset uploaded: {dataset_id}")

    # Show summary
    if st.button("Show Summary"):
        summary = client.get_summary(dataset_id)
        st.dataframe(summary)

    # Run agent
    if st.button("Run Agent"):
        result = client.run_agent(dataset_id)
        st.write(result['summary'])
        recs = client.get_recommendations(result['run_id'])
        st.dataframe(recs)
```

### Pattern 2: Scheduled Agent Jobs

```python
# scheduled_agent.py
from api_client import AgentClient
import schedule
import time

agent = AgentClient("http://localhost:8000")

def weekly_analysis():
    """Run every week to generate draft orders."""
    print("Running weekly analysis...")

    # Ingest latest data
    dataset_id = agent.ingest_data(["latest_week.xlsx"])

    # Analyze
    analysis = agent.analyze_inventory(dataset_id)

    # Make decisions
    decisions = agent.make_decisions(dataset_id)

    # Log results
    print(f"Analysis complete: {decisions['summary']}")

    # Could email results, post to Slack, etc.

# Schedule
schedule.every().monday.at("09:00").do(weekly_analysis)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### Pattern 3: External System Integration

```python
# integration_example.py
from api_client import InventoryClient

def sync_from_erp_to_inventory_api():
    """Example: Pull data from ERP and push to inventory API."""
    client = InventoryClient("http://localhost:8000")

    # Get data from your ERP system
    erp_data = get_data_from_erp()  # Your ERP API

    # Convert to Excel format
    excel_file = convert_to_excel(erp_data)

    # Upload to inventory API
    dataset_id = client.upload_files([excel_file])

    # Run analysis
    result = client.run_agent(dataset_id)

    # Get recommendations
    recs = client.get_recommendations(result['run_id'])

    # Push back to ERP for PO creation
    push_to_erp(recs)  # Your ERP API
```

### Pattern 4: Multi-Agent Coordination

```python
# multi_agent_system.py
from api_client import AgentClient

# Agent 1: Analysis Agent
analysis_agent = AgentClient("http://localhost:8000")
dataset_id = analysis_agent.ingest_data(["current_week.xlsx"])
analysis = analysis_agent.analyze_inventory(dataset_id)

# Agent 2: Decision Agent
decision_agent = AgentClient("http://localhost:8000")
decisions = decision_agent.make_decisions(dataset_id)

# Agent 3: Approval Agent (could use ML to auto-approve high-confidence items)
approval_agent = AgentClient("http://localhost:8000")
recs = approval_agent.get_decision_details(decisions['run_id'])

auto_approved = []
needs_review = []

for rec in recs:
    if rec['confidence'] == 'high' and rec['recommended_qty'] < 100:
        auto_approved.append(rec)
    else:
        needs_review.append(rec)

print(f"Auto-approved: {len(auto_approved)}")
print(f"Needs human review: {len(needs_review)}")

# Submit auto-approved items
if auto_approved:
    approval_agent.submit_order(decisions['run_id'], auto_approved)
```

---

## Key Differences: Human vs Agent Usage

| Aspect | Human Client | Agent Client |
|--------|-------------|--------------|
| **Method Names** | `upload_files()`, `get_summary()` | `ingest_data()`, `analyze_inventory()` |
| **Focus** | Interactive exploration | Autonomous operation |
| **Error Handling** | User-friendly messages | Structured for automation |
| **Return Values** | Display-ready data | Structured for processing |
| **Workflow** | Manual steps | Automated pipelines |

**Both clients use the same underlying API endpoints**, ensuring:
- ✅ Humans can see exactly what agents are doing
- ✅ Agents use the same tools as humans
- ✅ Consistent behavior across interfaces
- ✅ Easy debugging and monitoring

---

## Next Steps

1. **Start the API**: `python api_comprehensive.py`
2. **Explore the docs**: Open `http://localhost:8000/docs`
3. **Try examples**: Copy-paste examples above
4. **Build integrations**: Use the client library in your workflows

For more information, see:
- `api_comprehensive.py` - Full API implementation
- `api_client.py` - Python client library
- `/docs` endpoint - Interactive API documentation
