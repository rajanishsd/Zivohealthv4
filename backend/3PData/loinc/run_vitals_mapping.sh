#!/bin/bash

# Vitals Mapping Table Setup Script
# This script creates and populates the vitals_mappings table

set -e

echo "🏥 Setting up Vitals Mapping Table..."

# Change to the script directory
cd "$(dirname "$0")"

# Check if we're in the right directory
if [ ! -f "create_vitals_mapping.py" ]; then
    echo "❌ Error: create_vitals_mapping.py not found in current directory"
    exit 1
fi

# Load environment variables from backend
if [ -f "../.env" ]; then
    echo "📄 Loading environment variables from ../.env"
    export $(grep -v '^#' ../.env | xargs)
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is not installed"
    exit 1
fi

echo "🚀 Creating and populating vitals_mappings table..."

# Run the vitals mapping setup
python3 create_vitals_mapping.py --setup

echo "✅ Vitals mapping table setup completed!"
echo ""
echo "📋 To view the vitals mappings, run:"
echo "   python3 create_vitals_mapping.py --show"
echo ""
echo "🔧 Available commands:"
echo "   --create-table  : Create the table only"
echo "   --populate      : Populate the table with data"
echo "   --show          : Display all vitals mappings"
echo "   --setup         : Create table and populate (default)" 