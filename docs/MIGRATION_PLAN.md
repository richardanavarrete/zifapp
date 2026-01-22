# HoundCOGS API-First Migration Plan

This document provides a step-by-step migration plan to convert HoundCOGS from a monolithic Streamlit app to an API-first architecture.

---

## Overview

### Current State
- **Single file**: `zifapp.py` (2,396 lines) with UI + business logic interleaved
- **Supporting modules**: `agent.py`, `policy.py`, `storage.py`, etc. (fairly well-separated)
- **Existing API**: `sales-mix-api/` (proof that FastAPI works in this project)

### Target State
- **Core package**: `houndcogs/` - pure Python business logic
- **API layer**: `api/` - FastAPI REST endpoints
- **UI layer**: `ui/` - thin Streamlit client calling the API
- **Deployment**: Docker containers for API + UI

### Migration Strategy
**Parallel development** - build the new architecture alongside the existing app, then switch over.

---

## Phase 1: Isolate Core Logic (Foundation)

### Goal
Extract business logic from Streamlit files into the `houndcogs/` package.

### Tasks

#### 1.1 Set Up Package Structure
```bash
# Already created - verify structure
ls -la houndcogs/
ls -la houndcogs/models/
ls -la houndcogs/services/
ls -la houndcogs/storage/
```

#### 1.2 Migrate Data Models
Move existing dataclasses from `models.py` to Pydantic models:

| Source File | Target Location | Status |
|-------------|-----------------|--------|
| `models.py:Item` | `houndcogs/models/inventory.py` | Skeleton created |
| `models.py:WeeklyRecord` | `houndcogs/models/inventory.py` | Skeleton created |
| `models.py:InventoryDataset` | `houndcogs/models/inventory.py` | Skeleton created |
| `models.py:VoiceCountSession` | `houndcogs/models/voice.py` | Skeleton created |

**Action items:**
1. Read existing `models.py` and map each class
2. Convert `@dataclass` to Pydantic `BaseModel`
3. Add validation where needed
4. Ensure backward compatibility

#### 1.3 Migrate Services

| Source File | Target Location | Priority |
|-------------|-----------------|----------|
| `features.py` | `houndcogs/services/feature_engine.py` | High |
| `policy.py` | `houndcogs/services/policy_engine.py` | High |
| `agent.py` | `houndcogs/services/ordering_agent.py` | High |
| `cogs.py` | `houndcogs/services/cogs_analyzer.py` | Medium |
| `voice_matcher.py` | `houndcogs/services/fuzzy_matcher.py` | Medium |
| `audio_processing.py` | `houndcogs/services/audio_processor.py` | Medium |
| Excel parsing from `zifapp.py` | `houndcogs/services/inventory_parser.py` | High |

**Action items for each service:**
1. Copy function implementations
2. Remove Streamlit dependencies (`st.cache_data`, `st.session_state`)
3. Use Pydantic models for input/output
4. Add type hints
5. Write unit tests

#### 1.4 Migrate Storage Layer

| Source File | Target Location |
|-------------|-----------------|
| `storage.py` | `houndcogs/storage/sqlite_repo.py` |

**Action items:**
1. Keep SQLite for Phase 1 (simple)
2. Abstract file operations into `file_storage.py`
3. Ensure all DB operations are in one place

### Validation Criteria
- [ ] All unit tests pass
- [ ] No `import streamlit` in `houndcogs/`
- [ ] Core logic can run without Streamlit installed

---

## Phase 2: Build FastAPI Layer

### Goal
Wrap core logic in REST endpoints.

### Tasks

#### 2.1 Complete Endpoint Implementation

The API skeletons are created. Implement each by connecting to services:

```python
# Example: inventory.py router

from houndcogs.services.inventory_parser import parse_inventory_file
from houndcogs.storage.sqlite_repo import save_dataset, get_dataset

@router.post("/upload")
async def upload_inventory(file: UploadFile):
    # 1. Save file
    file_path = await file_storage.save_upload(file, dataset_id, filename)

    # 2. Parse file (calls core logic)
    dataset, warnings = parse_inventory_file(file_path, dataset_id, name)

    # 3. Store in database
    save_dataset(dataset)

    # 4. Return result
    return UploadResult(...)
```

#### 2.2 Priority Endpoints (MVP)

| Endpoint | Dependency | Implementation Order |
|----------|------------|----------------------|
| `GET /health` | None | 1 |
| `POST /inventory/upload` | File storage + Parser | 2 |
| `GET /inventory/datasets` | SQLite repo | 3 |
| `POST /orders/recommend` | Feature engine + Policy | 4 |
| `POST /voice/transcribe` | Audio processor | 5 |
| `POST /voice/match` | Fuzzy matcher | 6 |

#### 2.3 Add Integration Tests

```bash
# Run tests
pytest tests/integration/ -v
```

### Validation Criteria
- [ ] All MVP endpoints return valid responses
- [ ] File upload works end-to-end
- [ ] Order recommendations match existing behavior
- [ ] OpenAPI docs at `/docs` are accurate

---

## Phase 3: Refactor Streamlit as API Client

### Goal
Replace direct function calls with API calls.

### Tasks

#### 3.1 Start with One Tab

Pick the simplest tab and migrate it:

1. **Inventory Tab** (recommended start)
   - Replace `load_excel_file()` with `client.upload_inventory()`
   - Replace `compute_features()` with `client.analyze_dataset()`

```python
# Before (in zifapp.py)
dataset = load_inventory(uploaded_file)
features = compute_features(dataset)

# After (in ui/pages/inventory.py)
client = get_client()
result = client.upload_inventory(uploaded_file, filename)
if result.success:
    features_result = client.analyze_dataset(result.data['dataset_id'])
```

#### 3.2 Migration Order

1. **Inventory** - file upload, dataset listing
2. **Orders** - recommendations, approval
3. **COGS** - analysis, pour costs
4. **Voice** - transcription, matching (most complex)

#### 3.3 Handle Session State

Move session state to API:
- Use API-stored session IDs instead of `st.session_state`
- Cache results in browser with Streamlit, but source of truth is API

#### 3.4 Parallel Running

During migration, support both modes:

```python
# ui/config.py
USE_API = os.environ.get("USE_API", "true").lower() == "true"

# In page code
if USE_API:
    result = client.get_recommendations(dataset_id)
else:
    result = run_agent(dataset)  # Legacy direct call
```

### Validation Criteria
- [ ] UI shows same data as before
- [ ] File uploads work through API
- [ ] No functionality regression
- [ ] Performance acceptable (add loading indicators)

---

## Phase 4: Deployment

### Goal
Deploy API + UI with Docker.

### Tasks

#### 4.1 Local Docker Testing

```bash
# Build and run
cd zifapp
docker-compose -f docker/docker-compose.dev.yml up --build

# Test
curl http://localhost:8000/health
open http://localhost:8501
```

#### 4.2 Production Configuration

1. **Environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with production values
   ```

2. **API Keys**
   ```bash
   # Generate secure API key
   python -c "import secrets; print(f'hc_{secrets.token_urlsafe(24)}')"
   ```

3. **CORS origins** - restrict to your domain

#### 4.3 Deployment Options

**Option A: Single VPS (Recommended for MVP)**
```bash
# On your VPS
git pull
docker-compose -f docker/docker-compose.yml up -d
```

**Option B: Render.com**
```yaml
# render.yaml
services:
  - type: web
    name: houndcogs-api
    env: docker
    dockerfilePath: docker/Dockerfile.api
    envVars:
      - key: API_KEYS
        sync: false

  - type: web
    name: houndcogs-ui
    env: docker
    dockerfilePath: docker/Dockerfile.ui
    envVars:
      - key: UI_API_BASE_URL
        value: https://houndcogs-api.onrender.com
```

**Option C: Fly.io**
```bash
fly launch --dockerfile docker/Dockerfile.api
fly deploy
```

#### 4.4 Database Considerations

For Phase 1, SQLite is fine (single VPS).

For scaling:
1. Switch to PostgreSQL (Supabase, Railway, or managed)
2. Update `DATABASE_URL` environment variable
3. No code changes needed if using SQLAlchemy

### Validation Criteria
- [ ] Docker containers build successfully
- [ ] Health checks pass
- [ ] API accessible from UI container
- [ ] Data persists across restarts

---

## Testing Strategy

### Unit Tests
```bash
# Run all unit tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ --cov=houndcogs --cov-report=html
```

### Integration Tests
```bash
# Start API first
uvicorn api.main:app &

# Run integration tests
pytest tests/integration/ -v
```

### End-to-End Tests
```bash
# Use Docker for E2E
docker-compose -f docker/docker-compose.dev.yml up -d
pytest tests/e2e/ -v
```

### Manual Testing Checklist

- [ ] Upload inventory Excel file
- [ ] View dataset list
- [ ] Run order recommendations
- [ ] Approve recommendations
- [ ] Upload and transcribe audio
- [ ] Match voice text to items
- [ ] Export session data
- [ ] COGS analysis with sales mix

---

## API Versioning

### Current: v1
All endpoints under `/api/v1/`

### Adding v2 (Future)
```python
# api/main.py
app.include_router(inventory_v2.router, prefix="/api/v2/inventory", tags=["Inventory v2"])
```

### Deprecation Process
1. Mark v1 endpoints as deprecated in OpenAPI
2. Add `Deprecation` header to responses
3. Log usage of deprecated endpoints
4. Remove after migration period

---

## Rollback Plan

### If API Has Issues
1. Set `USE_API=false` in UI environment
2. UI falls back to direct function calls
3. Debug API separately

### If Need Full Rollback
1. Stop new containers
2. Start original `streamlit run zifapp.py`
3. Data in SQLite is still compatible

---

## Timeline Recommendations

| Phase | Estimated Effort | Dependencies |
|-------|------------------|--------------|
| Phase 1: Core Logic | 3-5 days | None |
| Phase 2: API Layer | 2-3 days | Phase 1 |
| Phase 3: UI Refactor | 3-5 days | Phase 2 |
| Phase 4: Deployment | 1-2 days | Phase 3 |
| **Total** | **9-15 days** | |

### Parallel Work Opportunities
- Phase 1 + Phase 2 API skeletons (can develop simultaneously)
- UI migration (can do one tab at a time)
- Docker setup (independent of code)

---

## Next Steps (Immediate Actions)

1. **Copy existing logic into skeletons**
   - Start with `features.py` → `feature_engine.py`
   - Run existing tests against new location

2. **Implement first endpoint end-to-end**
   - `POST /inventory/upload`
   - Test with real Excel file

3. **Set up CI/CD**
   - GitHub Actions for tests
   - Auto-deploy to staging on push

4. **Start using the new UI**
   - Deploy locally with `docker-compose`
   - Migrate one workflow at a time

---

## Appendix: File Mapping

### Original → New Location

```
models.py                    → houndcogs/models/inventory.py, orders.py, cogs.py, voice.py
features.py                  → houndcogs/services/feature_engine.py
agent.py                     → houndcogs/services/ordering_agent.py
policy.py                    → houndcogs/services/policy_engine.py
storage.py                   → houndcogs/storage/sqlite_repo.py
cogs.py                      → houndcogs/services/cogs_analyzer.py
voice_counting_ui.py         → ui/pages/voice.py (UI only)
voice_matcher.py             → houndcogs/services/fuzzy_matcher.py
audio_processing.py          → houndcogs/services/audio_processor.py
utils/sales_mix_parser.py    → houndcogs/services/inventory_parser.py (merge)
config/*.py                  → houndcogs/config/*.py (copy as-is)
zifapp.py                    → ui/app.py + ui/pages/*.py (split)
```

### Files to Delete After Migration
- `zifapp.py` (replaced by `ui/app.py`)
- `voice_counting_ui.py` (UI moved to `ui/pages/voice.py`)
- `sales-mix-api/` (merged into main API)
