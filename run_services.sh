#!/bin/bash

# Run both Zifapp and Sales Mix API services
# This script starts both services in the background and provides instructions to stop them

echo "🚀 Starting Zifapp Services..."
echo ""

# Check if sales-mix-api exists
if [ ! -d "sales-mix-api" ]; then
    echo "❌ Error: sales-mix-api directory not found!"
    exit 1
fi

# Start Sales Mix API
echo "📡 Starting Sales Mix API on port 8001..."
cd sales-mix-api
python main.py &
API_PID=$!
cd ..

# Wait a moment for API to start
sleep 2

# Start Streamlit app
echo "🎨 Starting Zifapp Streamlit interface on port 8501..."
streamlit run zifapp.py &
STREAMLIT_PID=$!

echo ""
echo "✅ Services started successfully!"
echo ""
echo "📊 Zifapp UI: http://localhost:8501"
echo "📡 Sales Mix API: http://localhost:8001"
echo "📖 API Docs: http://localhost:8001/docs"
echo ""
echo "Process IDs:"
echo "  - Sales Mix API: $API_PID"
echo "  - Streamlit: $STREAMLIT_PID"
echo ""
echo "To stop the services, run:"
echo "  kill $API_PID $STREAMLIT_PID"
echo ""
echo "Or press Ctrl+C and then run:"
echo "  pkill -f 'python main.py'"
echo "  pkill -f 'streamlit run'"
echo ""

# Wait for both processes
wait
