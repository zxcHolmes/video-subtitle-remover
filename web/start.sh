#!/bin/bash

# Start script for Video Subtitle Remover Web

set -e

echo "================================"
echo "Video Subtitle Remover Web"
echo "================================"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "Error: Node.js is not installed"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -q -r requirements.txt
pip install -q -r web/requirements-web.txt

# Build frontend if not exists
if [ ! -d "web/frontend/dist" ]; then
    echo "Building frontend..."
    cd web/frontend
    npm install
    npm run build
    cd ../..
fi

# Start server
echo "================================"
echo "Starting server on http://localhost:8000"
echo "Press Ctrl+C to stop"
echo "================================"

cd web/server
uvicorn main:app --host 0.0.0.0 --port 8000
