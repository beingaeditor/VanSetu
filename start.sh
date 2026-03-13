#!/bin/bash
# Start script for VanSetu Platform

echo "🌿 VanSetu Platform"
echo "================================="

# Check if we're in the right directory
if [ ! -f "delhi_ndvi_10m.tif" ]; then
    echo "❌ Error: Data files not found. Run this script from the van-setu-master directory."
    exit 1
fi

# Start backend in background
echo "📦 Starting backend server..."
cd backend
if [ ! -d "venv" ]; then
    echo "   Creating virtual environment..."
    python -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt -q
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 3

# Start frontend
echo "🎨 Starting frontend server..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ Services started!"
echo "   Frontend: http://localhost:5173"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services."

# Trap Ctrl+C to clean up
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

# Wait for processes
wait
