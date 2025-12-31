# Bev Usage Analyzer

A Streamlit application for analyzing beverage inventory usage and generating order recommendations.

## Features

- **Usage Summary**: View inventory metrics with filtering by vendor or category
- **Ordering Worksheet**: Interactive planning tool for inventory orders
- **Automated Calculations**: Tracks weeks of supply based on various usage averages
- **Data Export**: Download summaries and order lists as CSV files

## Installation

1. Clone the repository:
```bash
git clone [your-repo-url]
cd bev-usage-analyzer
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
streamlit run zifapp.py
```

## Usage

1. Upload your BEVWEEKLY Excel file
2. View the Usage Summary to analyze current inventory status
3. Use the Ordering Worksheet to plan your orders
4. Export your data as needed

## Configuration Files

- `vendor_map.json`: Maps items to their respective vendors
- `inventory_layout.json`: Defines the physical layout of inventory

## Data Requirements

Your Excel file should contain:
- Item names in the first column
- Usage data in column 10 (index 9)
- End Inventory in column 8 (index 7)
- Date information in row 2

## Development

This application uses:
- Streamlit for the web interface
- Pandas for data processing
- OpenPyXL for Excel file handling

## License

[Your chosen license]
