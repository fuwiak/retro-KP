#!/bin/bash

# Start FastAPI backend server

echo "Starting Retro Drawing Analyzer Backend..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "   Copy env.example to .env and configure GROQ_API_KEY"
    echo ""
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies if needed
if [ ! -d "venv/lib" ] || [ ! -f "venv/bin/uvicorn" ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Start server
echo "Starting server on http://localhost:3000"
echo "API docs available at http://localhost:3000/docs"
echo ""
python main.py

