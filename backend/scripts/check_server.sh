#!/bin/bash

echo "🔍 ZivoHealth Server Status Checker"
echo "===================================="

# Function to check port 8000
check_port_8000() {
    echo ""
    echo "🔌 Port 8000 Status:"
    PID=$(lsof -ti:8000)
    if [ ! -z "$PID" ]; then
        echo "✅ Port 8000 is in use by process $PID"
        echo "📋 Process details:"
        ps -p $PID
    else
        echo "❌ Port 8000 is not in use"
    fi
}

# Function to check uvicorn processes
check_uvicorn() {
    echo ""
    echo "🐍 Uvicorn Processes:"
    UVICORN_PIDS=$(pgrep -f uvicorn)
    if [ ! -z "$UVICORN_PIDS" ]; then
        echo "✅ Found uvicorn processes:"
        ps -p $UVICORN_PIDS
    else
        echo "❌ No uvicorn processes found"
    fi
}

# Function to check app processes
check_app_processes() {
    echo ""
    echo "🏥 ZivoHealth App Processes:"
    APP_PIDS=$(pgrep -f "app.main")
    if [ ! -z "$APP_PIDS" ]; then
        echo "✅ Found app.main processes:"
        ps -p $APP_PIDS
    else
        echo "❌ No app.main processes found"
    fi
}

# Function to test server endpoint
test_server() {
    echo ""
    echo "🌐 Server Connectivity Test:"
    if command -v curl > /dev/null; then
        echo "📡 Testing http://localhost:8000/docs..."
        HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 http://localhost:8000/docs)
        if [ "$HTTP_STATUS" = "200" ]; then
            echo "✅ Server is responding (HTTP $HTTP_STATUS)"
            echo "🔗 API Documentation: http://localhost:8000/docs"
        else
            echo "❌ Server not responding or error (HTTP $HTTP_STATUS)"
        fi
    else
        echo "⚠️  curl not available, skipping connectivity test"
    fi
}

# Function to check virtual environment
check_venv() {
    echo ""
    echo "🐍 Python Environment:"
    if [[ "$VIRTUAL_ENV" == "" ]]; then
        echo "❌ No virtual environment active"
        if [ -f "venv/bin/activate" ]; then
            echo "💡 Found venv at: ./venv/bin/activate"
        elif [ -f "../venv/bin/activate" ]; then
            echo "💡 Found venv at: ../venv/bin/activate"
        fi
    else
        echo "✅ Virtual environment active: $VIRTUAL_ENV"
    fi
}

# Run all checks
check_port_8000
check_uvicorn
check_app_processes
test_server
check_venv

echo ""
echo "📋 Summary:"
echo "   • To start server: ./backend/scripts/start_server.sh"
echo "   • To kill servers: ./backend/scripts/kill_servers.sh"
echo "   • To restart: ./backend/scripts/restart_server.sh" 