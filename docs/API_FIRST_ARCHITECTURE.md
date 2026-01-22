# HoundCOGS API-First Architecture

## Executive Summary

This document outlines the migration from a monolithic Streamlit application to an API-first architecture with:
- **Core Package**: Pure Python business logic (no framework dependencies)
- **FastAPI Backend**: RESTful API exposing all capabilities
- **Streamlit Client**: Thin UI layer that consumes the API

---

## Target Folder Structure

```
zifapp/
├── houndcogs/                      # Core business logic package (NEW)
│   ├── __init__.py
│   ├── models/                     # Pydantic models
│   │   ├── __init__.py
│   │   ├── inventory.py            # Item, WeeklyRecord, InventoryDataset
│   │   ├── orders.py               # OrderTargets, OrderConstraints, Recommendation
│   │   ├── cogs.py                 # COGSSummary, PourCostAnalysis
│   │   ├── voice.py                # VoiceSession, VoiceCountRecord
│   │   └── common.py               # Shared types, enums
│   ├── services/                   # Business logic (pure functions)
│   │   ├── __init__.py
│   │   ├── inventory_parser.py     # Excel/CSV parsing
│   │   ├── feature_engine.py       # Metrics computation
│   │   ├── ordering_agent.py       # Order recommendations
│   │   ├── policy_engine.py        # Decision rules
│   │   ├── cogs_analyzer.py        # COGS calculations
│   │   ├── voice_processor.py      # Voice counting logic
│   │   ├── fuzzy_matcher.py        # Item matching
│   │   └── audio_processor.py      # Audio transcription
│   ├── storage/                    # Data persistence
│   │   ├── __init__.py
│   │   ├── sqlite_repo.py          # SQLite operations
│   │   └── file_storage.py         # File handling (local/S3)
│   ├── config/                     # Reference data (moved from root)
│   │   ├── __init__.py
│   │   ├── constants.py
│   │   ├── product_maps.py         # Consolidated product definitions
│   │   └── vendor_categories.py
│   └── utils/                      # Shared utilities
│       ├── __init__.py
│       └── helpers.py
│
├── api/                            # FastAPI application (NEW)
│   ├── __init__.py
│   ├── main.py                     # FastAPI app entry point
│   ├── config.py                   # API configuration
│   ├── dependencies.py             # Dependency injection
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py                 # API key / JWT auth
│   │   ├── logging.py              # Request logging
│   │   └── errors.py               # Error handlers
│   ├── routers/                    # API endpoints
│   │   ├── __init__.py
│   │   ├── health.py               # Health checks
│   │   ├── inventory.py            # Inventory upload & analysis
│   │   ├── orders.py               # Order recommendations
│   │   ├── cogs.py                 # COGS analysis
│   │   ├── voice.py                # Voice counting
│   │   └── files.py                # File upload/download
│   └── schemas/                    # API-specific schemas
│       ├── __init__.py
│       ├── requests.py
│       └── responses.py
│
├── ui/                             # Streamlit client (REFACTORED)
│   ├── __init__.py
│   ├── app.py                      # Main Streamlit entry
│   ├── api_client.py               # HTTP client for API
│   ├── config.py                   # UI configuration
│   ├── pages/                      # Streamlit pages
│   │   ├── __init__.py
│   │   ├── inventory.py
│   │   ├── orders.py
│   │   ├── cogs.py
│   │   └── voice.py
│   └── components/                 # Reusable UI components
│       ├── __init__.py
│       ├── charts.py
│       └── tables.py
│
├── workers/                        # Background jobs (optional, Phase 2)
│   ├── __init__.py
│   ├── celery_app.py
│   └── tasks.py
│
├── tests/                          # Test suite
│   ├── __init__.py
│   ├── conftest.py                 # Pytest fixtures
│   ├── unit/
│   │   ├── test_inventory_parser.py
│   │   ├── test_feature_engine.py
│   │   ├── test_policy_engine.py
│   │   └── test_cogs_analyzer.py
│   ├── integration/
│   │   ├── test_api_inventory.py
│   │   ├── test_api_orders.py
│   │   └── test_api_voice.py
│   └── fixtures/                   # Test data files
│       ├── sample_inventory.xlsx
│       └── sample_sales.csv
│
├── scripts/                        # Utility scripts
│   ├── migrate_db.py
│   └── seed_data.py
│
├── docker/
│   ├── Dockerfile.api
│   ├── Dockerfile.ui
│   └── docker-compose.yml
│
├── .env.example                    # Environment template
├── pyproject.toml                  # Project config (replaces setup.py)
├── requirements.txt                # Dependencies (or use pyproject.toml)
└── README.md

# Legacy files (to be removed after migration)
├── zifapp.py                       # Original Streamlit app
├── models.py                       # → houndcogs/models/
├── agent.py                        # → houndcogs/services/ordering_agent.py
├── policy.py                       # → houndcogs/services/policy_engine.py
├── storage.py                      # → houndcogs/storage/sqlite_repo.py
├── features.py                     # → houndcogs/services/feature_engine.py
├── cogs.py                         # → houndcogs/services/cogs_analyzer.py
├── voice_counting_ui.py            # → ui/pages/voice.py
├── voice_matcher.py                # → houndcogs/services/fuzzy_matcher.py
├── audio_processing.py             # → houndcogs/services/audio_processor.py
└── config/                         # → houndcogs/config/
```

---

## API Endpoint Design

### Base URL: `/api/v1`

### Authentication
All endpoints (except `/health`) require API key in header:
```
X-API-Key: your-api-key-here
```

### Endpoints

#### Health & Status
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness check |
| GET | `/health/ready` | Readiness check (DB connected) |

#### Inventory Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/inventory/upload` | Upload Excel inventory file |
| GET | `/inventory/datasets` | List uploaded datasets |
| GET | `/inventory/datasets/{id}` | Get dataset details |
| DELETE | `/inventory/datasets/{id}` | Delete dataset |
| GET | `/inventory/items` | List all items with filters |
| GET | `/inventory/items/{item_id}` | Get item details + history |
| POST | `/inventory/analyze` | Run feature analysis on dataset |

#### Order Recommendations
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/orders/recommend` | Generate order recommendations |
| GET | `/orders/runs` | List past agent runs |
| GET | `/orders/runs/{run_id}` | Get specific run details |
| POST | `/orders/runs/{run_id}/approve` | Approve/modify recommendations |
| GET | `/orders/targets` | Get current order targets |
| PUT | `/orders/targets` | Update order targets |

#### COGS Analysis
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/cogs/analyze` | Run COGS analysis |
| POST | `/cogs/pour-cost` | Calculate pour costs |
| POST | `/cogs/variance` | Calculate usage variance |
| GET | `/cogs/reports` | List historical reports |
| GET | `/cogs/reports/{id}` | Get specific report |

#### Voice Counting
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/voice/sessions` | Create new counting session |
| GET | `/voice/sessions` | List sessions |
| GET | `/voice/sessions/{id}` | Get session details |
| PUT | `/voice/sessions/{id}` | Update session status |
| POST | `/voice/transcribe` | Transcribe audio file |
| POST | `/voice/match` | Match transcribed text to items |
| POST | `/voice/sessions/{id}/records` | Add count records |
| GET | `/voice/sessions/{id}/export` | Export session data |

#### File Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/files/{file_id}` | Download file |
| DELETE | `/files/{file_id}` | Delete file |

---

## Request/Response Examples

### POST /inventory/upload
```json
// Request: multipart/form-data
// file: inventory.xlsx

// Response: 201 Created
{
  "dataset_id": "ds_abc123",
  "filename": "inventory.xlsx",
  "items_count": 156,
  "weeks_count": 12,
  "date_range": {
    "start": "2024-01-07",
    "end": "2024-03-24"
  },
  "created_at": "2024-03-25T10:30:00Z"
}
```

### POST /orders/recommend
```json
// Request
{
  "dataset_id": "ds_abc123",
  "targets": {
    "weeks_by_category": {
      "Beer": 2,
      "Liquor": 4,
      "Wine": 3
    },
    "item_overrides": {
      "WHISKEY Buffalo Trace": 6
    }
  },
  "constraints": {
    "max_total_spend": 5000,
    "vendor_minimums": {
      "Breakthru": 500
    }
  }
}

// Response: 200 OK
{
  "run_id": "run_xyz789",
  "created_at": "2024-03-25T10:35:00Z",
  "summary": {
    "total_items": 42,
    "total_spend": 3847.50,
    "by_vendor": {
      "Breakthru": {"items": 15, "spend": 1200.00},
      "Southern": {"items": 12, "spend": 980.00}
    }
  },
  "recommendations": [
    {
      "item_id": "WHISKEY Buffalo Trace",
      "display_name": "Buffalo Trace",
      "category": "Whiskey",
      "vendor": "Breakthru",
      "current_on_hand": 2,
      "suggested_order": 4,
      "unit_cost": 22.50,
      "total_cost": 90.00,
      "reason_code": "STOCKOUT_RISK",
      "reason_text": "Below 1 week supply with high recent usage",
      "confidence": "high",
      "weeks_on_hand": 0.8,
      "avg_weekly_usage": 2.5
    }
  ],
  "warnings": [
    {"item_id": "VODKA Tito's", "message": "Data quality issue: negative usage in week 3"}
  ]
}
```

### POST /voice/transcribe
```json
// Request: multipart/form-data
// audio: recording.webm

// Response: 200 OK
{
  "transcription_id": "tr_def456",
  "text": "buffalo trace 2 bottles titos 3 bottles jameson 1 bottle",
  "duration_seconds": 12.5,
  "confidence": 0.94
}
```

### POST /voice/match
```json
// Request
{
  "text": "buffalo trace 2 bottles titos 3 bottles",
  "session_id": "sess_abc123"
}

// Response: 200 OK
{
  "matches": [
    {
      "raw_text": "buffalo trace 2 bottles",
      "matched_item": {
        "item_id": "WHISKEY Buffalo Trace",
        "display_name": "Buffalo Trace",
        "confidence": 0.98
      },
      "quantity": 2,
      "unit": "bottles"
    },
    {
      "raw_text": "titos 3 bottles",
      "matched_item": {
        "item_id": "VODKA Tito's",
        "display_name": "Tito's Vodka",
        "confidence": 0.95
      },
      "quantity": 3,
      "unit": "bottles"
    }
  ],
  "unmatched": []
}
```

---

## Storage Strategy

### Phase 1: Local Storage (Simple VPS Deployment)
```
data/
├── uploads/          # Uploaded files (Excel, CSV, audio)
│   └── {dataset_id}/
├── exports/          # Generated reports, CSVs
├── db/
│   └── houndcogs.db  # SQLite database
└── cache/            # Temporary processing files
```

### Phase 2: Cloud Storage (Scale-Out)
- **Files**: S3/MinIO with presigned URLs
- **Database**: PostgreSQL (managed, e.g., Supabase, Railway)
- **Cache**: Redis for sessions and computed features

### Caching Strategy
```python
# Cache layers:
# 1. In-memory (functools.lru_cache) - per-request
# 2. Redis/File cache - cross-request feature computations
# 3. Database - persistent results

CACHE_TTL = {
    "feature_computations": 3600,    # 1 hour
    "cogs_analysis": 1800,           # 30 min
    "fuzzy_match_index": 86400,      # 24 hours
}
```

---

## Background Jobs (Optional)

For long-running operations (>30s):
- Audio transcription of long recordings
- Full dataset reanalysis
- Batch report generation

### Simple Approach: RQ (Redis Queue)
```python
# Simpler than Celery, good for single-VPS deployment
from rq import Queue
from redis import Redis

redis_conn = Redis()
q = Queue(connection=redis_conn)

# Enqueue long-running task
job = q.enqueue(transcribe_audio, audio_file_path)
```

### Response Pattern
```json
// POST /voice/transcribe (long file)
{
  "job_id": "job_abc123",
  "status": "processing",
  "poll_url": "/jobs/job_abc123"
}

// GET /jobs/job_abc123
{
  "job_id": "job_abc123",
  "status": "completed",  // or "processing", "failed"
  "result": { ... },
  "progress": 100
}
```

---

## Authentication & Security

### Phase 1: API Key (Simple)
```python
# .env
API_KEYS=key1,key2,key3

# Header
X-API-Key: key1
```

### Phase 2: JWT (Multi-user)
```python
# Login endpoint returns JWT
POST /auth/login
{
  "username": "user@example.com",
  "password": "..."
}

# Response
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}

# Usage
Authorization: Bearer eyJ...
```

---

## Error Handling

### Standard Error Response
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid file format",
    "details": {
      "field": "file",
      "reason": "Expected .xlsx or .csv, got .pdf"
    }
  },
  "request_id": "req_abc123",
  "timestamp": "2024-03-25T10:30:00Z"
}
```

### Error Codes
| Code | HTTP Status | Description |
|------|-------------|-------------|
| VALIDATION_ERROR | 400 | Invalid input |
| AUTH_REQUIRED | 401 | Missing/invalid API key |
| FORBIDDEN | 403 | Valid key, insufficient permissions |
| NOT_FOUND | 404 | Resource not found |
| CONFLICT | 409 | Resource already exists |
| PROCESSING_ERROR | 422 | Valid input, but processing failed |
| RATE_LIMITED | 429 | Too many requests |
| INTERNAL_ERROR | 500 | Unexpected server error |

---

## Deployment Architecture

### Single VPS (Phase 1)
```
┌─────────────────────────────────────────────┐
│  VPS (e.g., Render, Fly.io, DigitalOcean)   │
│                                             │
│  ┌─────────────┐    ┌─────────────────┐    │
│  │  Streamlit  │───▶│    FastAPI      │    │
│  │  (port 8501)│    │  (port 8000)    │    │
│  └─────────────┘    └────────┬────────┘    │
│                              │              │
│                     ┌────────▼────────┐    │
│                     │    SQLite       │    │
│                     │  + Local Files  │    │
│                     └─────────────────┘    │
└─────────────────────────────────────────────┘
```

### Scaled (Phase 2)
```
┌──────────┐     ┌──────────────┐     ┌─────────────┐
│  CDN     │────▶│  Streamlit   │────▶│  FastAPI    │
│          │     │  (multiple)  │     │  (multiple) │
└──────────┘     └──────────────┘     └──────┬──────┘
                                             │
                      ┌──────────────────────┼──────────────────────┐
                      │                      │                      │
               ┌──────▼──────┐       ┌──────▼──────┐       ┌──────▼──────┐
               │  PostgreSQL │       │    Redis    │       │     S3      │
               │  (managed)  │       │   (cache)   │       │   (files)   │
               └─────────────┘       └─────────────┘       └─────────────┘
```

---

## Next Upgrades (Post-MVP)

1. **WebSocket Support** - Real-time voice transcription progress
2. **Multi-tenancy** - Organization/user isolation
3. **Audit Logging** - Track all data modifications
4. **Rate Limiting** - Per-key request limits
5. **API Versioning** - `/api/v2` for breaking changes
6. **OpenAPI Docs** - Auto-generated from FastAPI
7. **Webhook Notifications** - Notify on job completion
8. **LLM Integration** - Natural language explanations for recommendations
