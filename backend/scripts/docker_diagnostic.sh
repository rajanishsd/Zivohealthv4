#!/bin/bash

# Docker Diagnostic Script
# Run this to diagnose issues in your Docker container

set -e

echo "🐳 Docker Container Diagnostic Tool"
echo "=================================="

# Check if we're in a container
if [ -f /.dockerenv ]; then
    echo "✅ Running inside Docker container"
else
    echo "⚠️  Not running inside Docker container"
fi

echo ""
echo "📋 Container Information:"
echo "Hostname: $(hostname)"
echo "User: $(whoami)"
echo "Working Directory: $(pwd)"
echo "Python Version: $(python3 --version)"
echo "Timestamp: $(date)"

echo ""
echo "🔍 Running AWS Diagnostic Script..."
echo "=================================="

# Run the diagnostic script
python3 /app/scripts/aws_diagnostic.py

echo ""
echo "🔧 Quick Environment Check:"
echo "=========================="

# Quick environment variable check
echo "Critical Environment Variables:"
for var in SECRET_KEY VALID_API_KEYS POSTGRES_SERVER POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB POSTGRES_PORT DATABASE_URL ENVIRONMENT; do
    if [ -n "${!var}" ]; then
        if [[ "$var" == *"SECRET"* ]] || [[ "$var" == *"KEY"* ]] || [[ "$var" == *"PASSWORD"* ]] || [[ "$var" == *"URL"* ]]; then
            value="${!var}"
            masked="${value:0:8}...${value: -4}"
            echo "✅ $var: $masked"
        else
            echo "✅ $var: ${!var}"
        fi
    else
        echo "❌ $var: NOT SET"
    fi
done

echo ""
echo "🏁 Diagnostic Complete"
echo "===================="
echo "If you see any ❌ items above, those are the issues causing 401 errors."
echo "Set the missing environment variables and restart your container."
