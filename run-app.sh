#!/bin/bash

# Combined script to run both frontend and backend servers
echo "Starting Cheetah Market App..."

# Make script executable
chmod +x "$0"

# Start backend in background
cd cheetah-market-app/backend || exit 1
echo "Starting backend server..."
uvicorn main:app --reload --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 3

# Start frontend
cd ../frontend || exit 1
echo "Starting frontend server..."
npm run dev > frontend.log 2>&1 & 
FRONTEND_PID=$!

echo "Backend running with PID: $BACKEND_PID"
echo "Frontend running with PID: $FRONTEND_PID"
echo "Access the application at http://localhost:5173"

# Keep script running
wait
