# Sales Mix App Integration

This document explains how the Sales Mix app has been integrated into Zifapp as a separate API service.

## Architecture Overview

The Sales Mix functionality is implemented as a **microservice architecture** with two components:

1. **Sales Mix API** (`sales-mix-api/`) - A FastAPI backend service
2. **Discount Finder Tab** (in `zifapp.py`) - A Streamlit frontend that communicates with the API

```
┌─────────────────────────────────────┐
│                                     │
│         Zifapp (Streamlit)          │
│         Port: 8501                  │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  💵 Discount Finder Tab     │   │
│  │  (File Upload Interface)    │   │
│  └──────────┬──────────────────┘   │
│             │                       │
│             │ HTTP POST             │
│             │ /process              │
│             │                       │
└─────────────┼───────────────────────┘
              │
              │
              ▼
┌─────────────────────────────────────┐
│                                     │
│    Sales Mix API (FastAPI)          │
│    Port: 8001                       │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  Endpoints:                 │   │
│  │  - POST /process            │   │
│  │  - POST /process/csv        │   │
│  │  - GET /                    │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  sales_mix_processor.py     │   │
│  │  - Item categorization      │   │
│  │  - Price mapping            │   │
│  │  - Data processing          │   │
│  └─────────────────────────────┘   │
│                                     │
└─────────────────────────────────────┘
```

## Why Separate API?

The Sales Mix app is implemented as a separate API for several reasons:

1. **Service Independence**: The API can be used by other applications beyond Zifapp
2. **Scalability**: The API can be scaled independently from the main Streamlit app
3. **Maintainability**: Clear separation of concerns between UI and business logic
4. **Flexibility**: Can be deployed separately, versioned independently
5. **Reusability**: The API can be integrated into other systems (mobile apps, other dashboards, etc.)

## Directory Structure

```
zifapp/
├── zifapp.py                    # Main Streamlit app (includes Discount Finder tab)
├── requirements.txt             # Main app dependencies (includes requests)
├── run_services.sh              # Script to run both services
│
├── sales-mix-api/               # Sales Mix API service
│   ├── main.py                  # FastAPI application
│   ├── sales_mix_processor.py   # Core processing logic
│   ├── requirements.txt         # API dependencies
│   ├── run_api.sh               # Script to run API only
│   └── README.md                # API documentation
```

## Components

### 1. Sales Mix API (`sales-mix-api/`)

**Files:**
- `main.py`: FastAPI application with CORS-enabled endpoints
- `sales_mix_processor.py`: Contains all the item categorization and processing logic
- `requirements.txt`: FastAPI, uvicorn, pandas, python-multipart

**Endpoints:**
- `GET /`: Health check
- `POST /process`: Accepts CSV, returns JSON
- `POST /process/csv`: Accepts CSV, returns processed CSV

**Key Features:**
- Processes 400+ menu items across multiple categories
- Maps items to discount categories based on price points
- Returns both ordered (for export) and display (with visual breaks) formats

### 2. Discount Finder Tab (in `zifapp.py`)

**Location:** Lines 1875-2050 in `zifapp.py`

**Features:**
- File upload interface for CSV files
- Configurable API URL (defaults to localhost:8001)
- Real-time processing with progress indicators
- Data visualization with Plotly charts
- Download options for both formatted and raw data
- Error handling with helpful messages
- Instructions and documentation

**User Workflow:**
1. User uploads SalesMixByPrice.csv file
2. Tab sends file to Sales Mix API via HTTP POST
3. API processes and returns categorized data
4. Tab displays results with charts and metrics
5. User can download processed data

## Running the Services

### Option 1: Run Both Services Together

```bash
./run_services.sh
```

This starts:
- Sales Mix API on http://localhost:8001
- Zifapp Streamlit UI on http://localhost:8501

### Option 2: Run Services Separately

**Terminal 1 - Start API:**
```bash
cd sales-mix-api
python main.py
```

**Terminal 2 - Start Zifapp:**
```bash
streamlit run zifapp.py
```

### Option 3: Run API Only

```bash
cd sales-mix-api
./run_api.sh
```

## Installation

### Sales Mix API Dependencies

```bash
cd sales-mix-api
pip install -r requirements.txt
```

### Main App Dependencies

```bash
pip install -r requirements.txt
```

The main app's requirements.txt now includes `requests>=2.31.0` for making HTTP calls to the API.

## API Communication

The Discount Finder tab communicates with the API using the Python `requests` library:

```python
import requests

# Upload file to API
files = {"file": (filename, file_contents, "text/csv")}
response = requests.post(f"{api_url}/process", files=files, timeout=30)

# Parse response
if response.status_code == 200:
    result = response.json()
    display_data = pd.DataFrame(result["data"]["display"])
    ordered_data = pd.DataFrame(result["data"]["ordered"])
```

## Data Flow

1. **Upload**: User uploads CSV file in Streamlit interface
2. **API Call**: Tab sends file to `POST /process` endpoint
3. **Processing**: API processes file using `sales_mix_processor.py`
4. **Response**: API returns JSON with ordered and display data
5. **Visualization**: Tab displays results with charts and tables
6. **Download**: User can download processed data in CSV format

## Error Handling

The integration includes comprehensive error handling:

- **Connection Errors**: Clear message if API is not running
- **Timeout Errors**: 30-second timeout with user feedback
- **Processing Errors**: API errors are caught and displayed
- **Validation Errors**: Invalid CSV format errors are handled gracefully

## Configuration

### API URL Configuration

The API URL is configurable in the Streamlit interface:
- Default: `http://localhost:8001`
- Can be changed to point to a remote API server
- Useful for deployment scenarios

### CORS Configuration

The API is configured to allow requests from any origin (`*`). For production:

```python
# In sales-mix-api/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-streamlit-domain.com"],  # Specify exact origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Testing the Integration

1. **Start both services:**
   ```bash
   ./run_services.sh
   ```

2. **Access Zifapp:**
   Open http://localhost:8501

3. **Navigate to Discount Finder tab**

4. **Upload a test CSV file** with the expected format:
   - Header at row 4
   - Columns: Item, Price, Items Sold

5. **Verify:**
   - File uploads successfully
   - Processing completes
   - Results are displayed
   - Charts render correctly
   - Downloads work

## Deployment Considerations

### Development
- Run both services locally as described above
- API runs on port 8001, Streamlit on 8501

### Production Options

**Option 1: Same Server**
- Run both services on the same server using different ports
- Use a reverse proxy (nginx) to route requests
- Set API URL to localhost:8001

**Option 2: Separate Servers**
- Deploy API on dedicated server/container
- Update API URL in Streamlit interface
- Ensure proper CORS configuration
- Consider adding authentication

**Option 3: Containerized**
- Create Docker containers for each service
- Use Docker Compose to orchestrate
- Include nginx for routing

## Troubleshooting

### API Not Responding
- Check if API is running: `curl http://localhost:8001`
- Check API logs for errors
- Verify port 8001 is not in use

### Connection Errors in Streamlit
- Verify API URL is correct
- Check firewall/network settings
- Ensure API is accessible from Streamlit

### Processing Errors
- Check CSV file format (header at row 4)
- Verify required columns exist
- Check API logs for detailed error messages

## Future Enhancements

Potential improvements to the integration:

1. **Authentication**: Add API key or OAuth authentication
2. **Caching**: Cache processed results in Streamlit session
3. **Batch Processing**: Support multiple file uploads
4. **History**: Store and retrieve past processing results
5. **Webhooks**: Add webhook support for async processing
6. **Monitoring**: Add health checks and monitoring
7. **Rate Limiting**: Implement rate limiting on API
8. **Database**: Store results in database instead of memory

## References

- Original Sales Mix App: https://github.com/richardanavarrete/Sales-Mix_App
- FastAPI Documentation: https://fastapi.tiangolo.com/
- Streamlit Documentation: https://docs.streamlit.io/
- API Documentation (when running): http://localhost:8001/docs
