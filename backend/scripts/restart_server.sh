#!/bin/bash

echo "🔄 ZivoHealth Server Restart Script"
echo "=================================="

# Function to kill processes using port 8000
kill_port_8000() {
    echo "🔍 Checking for processes using port 8000..."
    PID=$(lsof -ti:8000)
    if [ ! -z "$PID" ]; then
        echo "💀 Killing process $PID using port 8000..."
        kill -9 $PID
        sleep 2
    else
        echo "✅ No processes found using port 8000"
    fi
}

# Function to kill uvicorn processes
kill_uvicorn() {
    echo "🔍 Checking for uvicorn processes..."
    UVICORN_PIDS=$(pgrep -f uvicorn)
    if [ ! -z "$UVICORN_PIDS" ]; then
        echo "💀 Killing uvicorn processes: $UVICORN_PIDS"
        pkill -f uvicorn
        sleep 2
    else
        echo "✅ No uvicorn processes found"
    fi
}

# Function to kill python processes running our app
kill_app_processes() {
    echo "🔍 Checking for app.main processes..."
    APP_PIDS=$(pgrep -f "app.main")
    if [ ! -z "$APP_PIDS" ]; then
        echo "💀 Killing app.main processes: $APP_PIDS"
        pkill -f "app.main"
        sleep 2
    else
        echo "✅ No app.main processes found"
    fi
}

# Step 1: Kill existing servers
echo ""
echo "📊 Step 1: Stopping existing servers..."
kill_uvicorn
kill_app_processes
kill_port_8000

# Step 2: Verify port is free
echo ""
echo "🔍 Step 2: Verifying port 8000 is free..."
PORT_CHECK=$(lsof -ti:8000)
if [ ! -z "$PORT_CHECK" ]; then
    echo "⚠️  Port 8000 still in use, forcing kill..."
    kill -9 $PORT_CHECK
    sleep 2
fi

# Step 3: Check if we're in the right directory
echo ""
echo "📁 Step 3: Checking directory structure..."
if [ -d "backend" ]; then
    echo "✅ Found backend directory"
elif [ -f "app/main.py" ]; then
    echo "✅ Already in backend directory"
else
    echo "❌ Error: Cannot find backend directory or app/main.py"
    echo "Please run this script from the zivohealth root directory"
    exit 1
fi

# Step 4: Start the server
echo ""
echo "🚀 Step 4: Starting backend server..."
if [ -d "backend" ]; then
    cd backend
fi

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  Virtual environment not detected. Trying to activate..."
    if [ -f "../venv/bin/activate" ]; then
        source ../venv/bin/activate
        echo "✅ Activated virtual environment"
    elif [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
        echo "✅ Activated virtual environment"
    else
        echo "⚠️  No virtual environment found, proceeding anyway..."
    fi
fi

echo "🌐 Starting uvicorn server on http://0.0.0.0:8000..."
echo "📝 Server logs will appear below. Press Ctrl+C to stop."
echo ""

# Start the server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 