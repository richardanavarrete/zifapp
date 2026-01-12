# API Architecture: Unified Interface for Humans and Agents

## 🎯 Core Principle

**Both humans and agents use the same API endpoints.**

This architectural decision ensures:
- ✅ Transparency: Humans can see what agents are doing
- ✅ Consistency: Same business logic for all callers
- ✅ Testability: Single codebase to test
- ✅ Flexibility: Easy to switch between manual and automated workflows

---

## 📊 Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                  FastAPI REST API                       │
│                (api_comprehensive.py)                   │
│                                                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐     │
│  │  Analytics  │ │    Agent    │ │ Preferences │     │
│  │  Endpoints  │ │  Endpoints  │ │  Endpoints  │     │
│  └─────────────┘ └─────────────┘ └─────────────┘     │
│          │              │               │              │
│  ┌──────────────────────────────────────────┐         │
│  │        Core Business Logic                │         │
│  │  (models, features, policy, storage)      │         │
│  └──────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────────┐      ┌─────────┐     ┌─────────┐
    │  Human  │      │  Agent  │     │  Other  │
    │ Client  │      │ Client  │     │ Systems │
    └─────────┘      └─────────┘     └─────────┘
         │                │                │
    ┌─────────┐      ┌─────────┐     ┌─────────┐
    │Streamlit│      │Scheduled│     │   ERP   │
    │   UI    │      │  Jobs   │     │Integration│
    └─────────┘      └─────────┘     └─────────┘
```

---

## 🔧 API Endpoints by Category

### 1. Data Management

| Endpoint | Method | Purpose | Human Use | Agent Use |
|----------|--------|---------|-----------|-----------|
| `/upload` | POST | Upload Excel files | Weekly data entry | Automated ingestion |
| `/datasets` | GET | List datasets | Browse history | Enumerate sources |
| `/datasets/{id}` | GET | Dataset info | View metadata | Validate ingestion |
| `/datasets/{id}` | DELETE | Remove dataset | Clean up old data | Free memory |

**Example:**
```python
# Human
client.upload_files(["week1.xlsx"])

# Agent
agent.ingest_data(["week1.xlsx"])

# Both call: POST /upload
```

### 2. Analytics

| Endpoint | Method | Purpose | Human Use | Agent Use |
|----------|--------|---------|-----------|-----------|
| `/analytics/{id}/summary` | GET | Item summaries | Dashboard table | State analysis |
| `/analytics/{id}/items/{item}` | GET | Item details | Deep dive view | Item inspection |
| `/analytics/{id}/trends` | GET | Trend stats | Trend dashboard | Pattern detection |
| `/analytics/{id}/chart/{item}` | GET | Time-series data | Visualization | Historical analysis |
| `/analytics/{id}/vendors` | GET | Vendor summary | Vendor comparison | Vendor analysis |
| `/analytics/{id}/categories` | GET | Category summary | Category view | Category distribution |

**Example:**
```python
# Human
summary = client.get_summary(dataset_id, vendor="Breakthru")

# Agent
analysis = agent.analyze_inventory(dataset_id)

# Both call: GET /analytics/{id}/summary
```

### 3. Agent Operations

| Endpoint | Method | Purpose | Human Use | Agent Use |
|----------|--------|---------|-----------|-----------|
| `/agent/run/{id}` | POST | Run agent | Generate draft order | Self-initiate |
| `/agent/runs` | GET | Run history | Review past orders | Decision history |
| `/agent/runs/{id}/recommendations` | GET | Get recs | Review & approve | Retrieve decisions |
| `/agent/runs/{id}/export` | GET | Export CSV | Download order | Generate file |

**Example:**
```python
# Human
result = client.run_agent(dataset_id)

# Agent
decisions = agent.make_decisions(dataset_id)

# Both call: POST /agent/run/{id}
```

### 4. Preferences & Actions

| Endpoint | Method | Purpose | Human Use | Agent Use |
|----------|--------|---------|-----------|-----------|
| `/preferences` | GET | Get all prefs | View settings | Load knowledge |
| `/preferences/{item}` | POST | Set preference | Customize targets | Store learned behavior |
| `/actions` | POST | Save actions | Record order | Learn from feedback |
| `/items/{item}/history` | GET | Item history | View past | Learn patterns |

**Example:**
```python
# Human
client.set_preference("WHISKEY Buffalo Trace", target_weeks_override=6.0)

# Agent
agent.learn_from_feedback(item_id, {"target_weeks_override": 6.0})

# Both call: POST /preferences/{item}
```

---

## 🔀 Client Library Design

### InventoryClient (Human-Focused)

**Philosophy:** Interactive, exploration-focused

```python
from api_client import InventoryClient

client = InventoryClient("http://localhost:8000")

# Method names match human mental model
client.upload_files(["week1.xlsx"])
summary = client.get_summary(dataset_id)
result = client.run_agent(dataset_id)
recs = client.get_recommendations(result['run_id'])
client.download_order(result['run_id'], "order.csv")
```

**Characteristics:**
- User-friendly method names
- Returns display-ready data
- Includes convenience methods (download_order)
- Error messages designed for humans

### AgentClient (Agent-Focused)

**Philosophy:** Autonomous, decision-focused

```python
from api_client import AgentClient

agent = AgentClient("http://localhost:8000")

# Method names match agent actions
agent.ingest_data(["week1.xlsx"])
analysis = agent.analyze_inventory(dataset_id)
decisions = agent.make_decisions(dataset_id)
details = agent.get_decision_details(decisions['run_id'])
agent.submit_order(decisions['run_id'], approved_items)
```

**Characteristics:**
- Action-oriented method names
- Returns structured data for processing
- Includes learning methods (learn_from_feedback)
- Error handling for automation

### Underlying Unity

**Both clients call the same HTTP endpoints:**

```python
# Human client
client.upload_files(["data.xlsx"])
# Calls: POST /upload

# Agent client
agent.ingest_data(["data.xlsx"])
# Calls: POST /upload

# Same endpoint, same data, same result
```

---

## 🚀 Deployment Scenarios

### Scenario 1: Local Development

```bash
# Terminal 1: Start API
python api_comprehensive.py

# Terminal 2: Use client
python
>>> from api_client import InventoryClient
>>> client = InventoryClient("http://localhost:8000")
>>> # Use normally
```

### Scenario 2: Streamlit UI + API Backend

```
┌──────────────┐         ┌──────────────┐
│  Streamlit   │  HTTP   │  FastAPI     │
│  Frontend    ├────────►│  Backend     │
│              │         │              │
└──────────────┘         └──────┬───────┘
                                │
                         ┌──────▼───────┐
                         │  Business    │
                         │  Logic       │
                         └──────────────┘
```

**Benefits:**
- UI can be replaced without changing logic
- Multiple UIs can share same backend
- API can be used independently of UI

### Scenario 3: Automated Agent + Human Oversight

```
┌──────────────┐         ┌──────────────┐
│  Scheduled   │         │              │
│  Agent       ├────────►│   FastAPI    │
│  (Cron Job)  │         │   Backend    │
└──────────────┘         │              │
                         └──────┬───────┘
┌──────────────┐                │
│  Human via   │                │
│  Web UI      ├────────────────┘
└──────────────┘
```

**Workflow:**
1. Agent runs nightly, generates recommendations
2. Human reviews via UI in morning
3. Human approves/modifies via same API
4. Agent learns from human edits

### Scenario 4: Full Automation

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   ERP        │    │   FastAPI    │    │   Vendor     │
│   System     ├───►│   Backend    ├───►│   Portal     │
│              │    │              │    │              │
└──────────────┘    └──────────────┘    └──────────────┘
       ▲                    │                    │
       │                    │                    │
       └────────────────────┴────────────────────┘
              Data flows automatically
```

**Workflow:**
1. ERP pushes inventory data to API
2. API generates recommendations
3. High-confidence orders auto-submitted to vendors
4. Low-confidence orders queue for human review

---

## 🔒 API Design Patterns

### Pattern 1: Consistent Response Format

```json
{
  "status": "success",
  "data": { ... },
  "metadata": {
    "timestamp": "2024-01-15T10:30:00Z",
    "processing_time_ms": 245
  }
}
```

### Pattern 2: Filtering & Pagination

```python
# All list endpoints support filtering
GET /analytics/{id}/summary?vendor=Breakthru&category=Whiskey

# All list endpoints support pagination (future enhancement)
GET /agent/runs?limit=10&offset=20
```

### Pattern 3: Bulk Operations

```python
# Multiple actions in one request
POST /actions
{
  "run_id": "abc123",
  "actions": [
    {"item_id": "item1", "recommended_qty": 10, "approved_qty": 12},
    {"item_id": "item2", "recommended_qty": 5, "approved_qty": 5},
    ...
  ]
}
```

### Pattern 4: Export Formats

```python
# Same data, different formats
GET /agent/runs/{id}/recommendations
# Returns: JSON

GET /agent/runs/{id}/export
# Returns: CSV

# Future: Excel, PDF exports
```

---

## 📈 Performance Considerations

### Caching Strategy

```python
# In-memory caching for expensive operations
_datasets: Dict[str, InventoryDataset] = {}
_features_cache: Dict[str, pd.DataFrame] = {}

# Cache key includes parameters
cache_key = f"{dataset_id}_{smoothing_level}_{trend_threshold}"
```

**Benefits:**
- Repeat requests are instant
- Reduces CPU for feature computation
- Shared across all clients

**Trade-offs:**
- Memory usage grows with datasets
- Manual clearing needed for updates
- Not suitable for multi-server deployment (yet)

### Async Support (Future)

```python
# Current (synchronous)
@app.post("/agent/run/{dataset_id}")
async def run_agent_endpoint(dataset_id: str, request: AgentRunRequest):
    result = run_agent(dataset_id)  # Blocks
    return result

# Future (async)
@app.post("/agent/run/{dataset_id}")
async def run_agent_endpoint(dataset_id: str, request: AgentRunRequest):
    result = await asyncio.to_thread(run_agent, dataset_id)
    return result
```

---

## 🛡️ Security Considerations

### Current State (Development)

```python
# CORS: Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ Change in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Production Recommendations

1. **Authentication:**
   ```python
   from fastapi import Depends, HTTPException, status
   from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

   security = HTTPBearer()

   async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
       if credentials.credentials != VALID_TOKEN:
           raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
       return credentials
   ```

2. **Rate Limiting:**
   ```python
   from slowapi import Limiter, _rate_limit_exceeded_handler
   from slowapi.util import get_remote_address

   limiter = Limiter(key_func=get_remote_address)
   app.state.limiter = limiter

   @app.post("/agent/run/{dataset_id}")
   @limiter.limit("10/minute")  # Max 10 runs per minute
   async def run_agent_endpoint(...):
       ...
   ```

3. **Input Validation:**
   ```python
   # Already implemented via Pydantic models
   class AgentRunRequest(BaseModel):
       usage_column: str = Field(default='avg_4wk', pattern='^avg_(ytd|10wk|4wk|2wk)$')
       smoothing_level: float = Field(default=0.3, ge=0.1, le=0.9)
   ```

---

## 📦 Deployment Options

### Option 1: Docker Container

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "api_comprehensive:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t inventory-api .
docker run -p 8000:8000 inventory-api
```

### Option 2: Cloud Functions (AWS Lambda, Google Cloud Functions)

```python
# lambda_handler.py
from mangum import Mangum
from api_comprehensive import app

handler = Mangum(app)
```

### Option 3: Traditional Server (systemd)

```ini
# /etc/systemd/system/inventory-api.service
[Unit]
Description=Inventory Management API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/inventory-api
ExecStart=/usr/local/bin/uvicorn api_comprehensive:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 🔍 Monitoring & Observability

### Logging

```python
import logging

logger = logging.getLogger(__name__)

@app.post("/agent/run/{dataset_id}")
async def run_agent_endpoint(dataset_id: str, request: AgentRunRequest):
    logger.info(f"Agent run started: dataset={dataset_id}, params={request.dict()}")

    try:
        result = run_agent(dataset, ...)
        logger.info(f"Agent run completed: run_id={result['run_id']}")
        return result
    except Exception as e:
        logger.error(f"Agent run failed: {e}", exc_info=True)
        raise
```

### Metrics (Future)

```python
from prometheus_client import Counter, Histogram

api_requests = Counter('api_requests_total', 'Total API requests', ['endpoint', 'method'])
api_latency = Histogram('api_latency_seconds', 'API request latency')

@app.middleware("http")
async def add_metrics(request: Request, call_next):
    with api_latency.time():
        response = await call_next(request)
    api_requests.labels(endpoint=request.url.path, method=request.method).inc()
    return response
```

---

## 🎯 Key Takeaways

1. **Unified API** = Same tools for humans and agents
2. **Client libraries** = Different interfaces, same functionality
3. **OpenAPI docs** = Self-documenting, easy to explore
4. **Production-ready** = Add auth, rate limiting, monitoring
5. **Extensible** = Easy to add new endpoints and features

---

## 📚 Related Documentation

- **API_USAGE_EXAMPLES.md** - Comprehensive usage examples
- **IMPLEMENTATION_SUMMARY.md** - Overall architecture overview
- **AGENT_REFACTOR_PLAN.md** - Technical blueprint

**Interactive docs**: Start the API and visit `http://localhost:8000/docs`
