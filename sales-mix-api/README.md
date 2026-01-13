# Sales Mix API

A FastAPI service that processes sales mix CSV files to generate EOM (End-of-Month) discount sheets.

## Overview

This API provides endpoints to process Point-of-Sale (POS) export CSV files and automatically categorize items into discount categories based on item types and price points.

## Features

- **CSV Processing**: Accepts CSV uploads with sales data
- **Item Categorization**: Maps 400+ menu items to appropriate discount categories
- **Price-based Grouping**: Groups items by category and price tier
- **Multiple Output Formats**: Returns both JSON and CSV formatted results
- **CORS Enabled**: Can be called from frontend applications

## API Endpoints

### `GET /`
Health check endpoint

**Response:**
```json
{
  "status": "ok",
  "service": "Sales Mix API",
  "version": "1.0.0"
}
```

### `POST /process`
Process a sales mix CSV file and return JSON data

**Parameters:**
- `file`: CSV file upload (multipart/form-data)

**Expected CSV Format:**
- Header starts at row 4 (0-indexed row 3)
- Required columns: Item name, Price, Items Sold

**Response:**
```json
{
  "status": "success",
  "data": {
    "ordered": [...],
    "display": [...]
  }
}
```

### `POST /process/csv`
Process a sales mix CSV file and return CSV output

**Parameters:**
- `file`: CSV file upload (multipart/form-data)

**Response:**
- Content-Type: text/csv
- Downloadable CSV file

## Installation

1. Install dependencies:
```bash
cd sales-mix-api
pip install -r requirements.txt
```

2. Run the API:
```bash
python main.py
```

Or use the run script:
```bash
chmod +x run_api.sh
./run_api.sh
```

The API will start on `http://localhost:8001`

## Integration with Zifapp

This API is designed to work with the Zifapp Streamlit application. The "Discount Finder" tab in Zifapp makes HTTP requests to this API to process sales mix files.

To run both services together:
```bash
cd ..
chmod +x run_services.sh
./run_services.sh
```

## API Documentation

Once the API is running, visit `http://localhost:8001/docs` for interactive API documentation (Swagger UI).

## Technology Stack

- **FastAPI**: Modern Python web framework
- **Pandas**: Data processing and analysis
- **Uvicorn**: ASGI server
- **Python 3.8+**: Required Python version

## Development

To modify the item categorization mappings, edit the dictionaries in `sales_mix_processor.py`:
- `item_to_category`: Maps menu items to categories
- `key_to_sheet_label`: Maps category-price combinations to discount labels
- `DESIRED_ORDER_FINAL_CSV`: Defines output ordering

## Error Handling

The API includes comprehensive error handling:
- Invalid CSV format → 400 Bad Request
- Missing required columns → 400 Bad Request
- Processing errors → 400 Bad Request with details

## Security Notes

- CORS is currently set to allow all origins (`*`)
- For production use, configure `allow_origins` to specific domains
- No authentication is currently implemented
- Suitable for internal use or behind authentication middleware
