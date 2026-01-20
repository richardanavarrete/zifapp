# smallCOGS

A clean, generic inventory management system with usage analytics.

**Works with any structured spreadsheet** - no hardcoded business logic.

## Features

- **Upload any inventory spreadsheet** (Excel or CSV)
- **Auto-detect columns** for item names, quantities, usage, categories
- **Usage analytics** with trends, rolling averages, and alerts
- **Drill-down views** for individual items with charts
- **Clean REST API** for programmatic access
- **Responsive Streamlit UI**

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
pip install -r requirements-ui.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings
```

### 3. Generate an API Key

```bash
python -c "import secrets; print(f'sc_{secrets.token_urlsafe(24)}')"
```

Add the generated key to your `.env` file.

### 4. Start the API

```bash
uvicorn api.main:app --reload
```

API will be available at `http://localhost:8000`

### 5. Start the UI

```bash
streamlit run ui/app.py
```

UI will be available at `http://localhost:8501`

## Docker

```bash
# Build and run both services
cd docker
docker-compose up --build

# Or run with environment variables
API_KEYS=your-key docker-compose up --build
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/v1/inventory/upload` | Upload inventory file |
| GET | `/api/v1/inventory/datasets` | List datasets |
| GET | `/api/v1/inventory/datasets/{id}` | Get dataset details |
| DELETE | `/api/v1/inventory/datasets/{id}` | Delete dataset |
| GET | `/api/v1/inventory/datasets/{id}/items` | Get items with stats |
| GET | `/api/v1/inventory/datasets/{id}/items/{item_id}` | Get item detail |
| GET | `/api/v1/inventory/datasets/{id}/dashboard` | Get dashboard stats |

All endpoints (except `/health`) require `X-API-Key` header.

## Spreadsheet Format

smallCOGS auto-detects columns. Your spreadsheet should have:

**Required:**
- Item/Product name column
- Quantity/On-hand column

**Optional (auto-detected):**
- Usage column
- Category column
- Date column
- Vendor column

## Project Structure

```
smallCOGS/
├── smallcogs/          # Core business logic
│   ├── models/         # Pydantic data models
│   └── services/       # Business logic services
├── api/                # FastAPI backend
│   ├── routers/        # API endpoints
│   └── middleware/     # Auth, logging
├── ui/                 # Streamlit frontend
│   └── pages/          # UI pages
├── docker/             # Docker configuration
└── data/               # Data storage
```

## Security

- API keys stored in environment variables only
- Secrets never committed to git
- CORS configured per environment
- Input validation on all endpoints

## License

MIT
