#!/bin/bash

# Development start script - runs backend and frontend separately

set -e

echo "================================"
echo "Video Subtitle Remover Web (Dev Mode)"
echo "================================"

# Function to cleanup background processes
cleanup() {
    echo "Stopping servers..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit
}

trap cleanup EXIT INT TERM

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

# Install frontend dependencies
echo "Installing frontend dependencies..."
cd web/frontend
npm install
cd ../..

# Start backend
echo "Starting backend on http://localhost:8000..."
cd web/server
uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ../..

# Wait for backend to start
sleep 2

# Start frontend
echo "Starting frontend on http://localhost:5173..."
cd web/frontend
npm run dev &
FRONTEND_PID=$!
cd ../..

echo "================================"
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "API Docs: http://localhost:8000/docs"
echo "================================"
echo "Press Ctrl+C to stop both servers"

# Wait for processes
wait
