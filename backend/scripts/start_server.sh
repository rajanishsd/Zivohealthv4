#!/bin/bash

echo "🚀 ZivoHealth Server Starter"
echo "============================"

# Check if we're in the right directory
echo ""
echo "📁 Checking directory structure..."
if [ -d "backend" ]; then
    echo "✅ Found backend directory"
    cd backend
elif [ -f "app/main.py" ]; then
    echo "✅ Already in backend directory"
else
    echo "❌ Error: Cannot find backend directory or app/main.py"
    echo "Please run this script from the zivohealth root directory"
    exit 1
fi

# Check if port 8000 is already in use
echo ""
echo "🔍 Checking if port 8000 is available..."
PORT_CHECK=$(lsof -ti:8000)
if [ ! -z "$PORT_CHECK" ]; then
    echo "⚠️  Port 8000 is already in use by process $PORT_CHECK"
    echo "💡 To kill existing servers first, run: ./backend/scripts/kill_servers.sh"
echo "💡 Or use the restart script: ./backend/scripts/restart_server.sh"
    exit 1
else
    echo "✅ Port 8000 is available"
fi

# Check if virtual environment is activated
echo ""
echo "🐍 Checking Python environment..."
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
else
    echo "✅ Virtual environment active: $VIRTUAL_ENV"
fi

echo ""
echo "🌐 Starting uvicorn server on http://0.0.0.0:8000..."
echo "📝 Server logs will appear below. Press Ctrl+C to stop."
echo "🔗 API Documentation: http://localhost:8000/docs"
echo ""

# Start the server using the virtual environment's Python
echo "🔍 Debug: Current working directory: $(pwd)"
echo "🔍 Debug: Checking Python paths..."
echo "🔍 Debug: VIRTUAL_ENV = $VIRTUAL_ENV"
echo "🔍 Debug: ../venv/bin/python exists: $([ -f "../venv/bin/python" ] && echo "YES" || echo "NO")"
echo "🔍 Debug: venv/bin/python exists: $([ -f "venv/bin/python" ] && echo "YES" || echo "NO")"
echo "🔍 Debug: which python3 = $(which python3)"

if [ -f "../venv/bin/python" ]; then
    echo "🔍 Debug: Using ../venv/bin/python"
    ../venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
elif [ -f "venv/bin/python" ]; then
    echo "🔍 Debug: Using venv/bin/python"
    venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
else
    echo "🔍 Debug: Using system python3"
    python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
fi