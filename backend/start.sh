#!/bin/bash
# Polis Backend Startup Script

echo "Starting Polis Backend..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "ERROR: .env file not found"
    echo "Please copy .env.example to .env and fill in your configuration"
    exit 1
fi

# Start server
echo "Starting uvicorn server on http://localhost:8000"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
