#!/bin/bash

echo "💀 ZivoHealth Server Killer"
echo "=========================="

# Function to kill processes using port 8000
kill_port_8000() {
    echo "🔍 Checking for processes using port 8000..."
    PID=$(lsof -ti:8000)
    if [ ! -z "$PID" ]; then
        echo "💀 Killing process $PID using port 8000..."
        kill -9 $PID
        sleep 1
        echo "✅ Process $PID killed"
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
        sleep 1
        echo "✅ Uvicorn processes killed"
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
        sleep 1
        echo "✅ App processes killed"
    else
        echo "✅ No app.main processes found"
    fi
}

echo ""
echo "🛑 Stopping all ZivoHealth servers..."
kill_uvicorn
kill_app_processes
kill_port_8000

echo ""
echo "🔍 Final verification..."
PORT_CHECK=$(lsof -ti:8000)
if [ ! -z "$PORT_CHECK" ]; then
    echo "⚠️  Port 8000 still in use, forcing kill..."
    kill -9 $PORT_CHECK
    sleep 1
    echo "✅ Port 8000 freed"
else
    echo "✅ Port 8000 is free"
fi

echo ""
echo "🎉 All servers stopped successfully!"
echo "📝 To restart the server, run: ./backend/scripts/start_server.sh" 