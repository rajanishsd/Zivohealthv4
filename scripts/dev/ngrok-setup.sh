#!/bin/bash

# ngrok Setup Script for ZivoHealth iOS Development
# This script starts ngrok tunnel for USB development

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 ZivoHealth ngrok Setup for USB Development${NC}"
echo "=============================================="

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo -e "${RED}❌ ngrok is not installed${NC}"
    echo "Please install ngrok first:"
    echo "  brew install ngrok"
    echo "  OR download from: https://ngrok.com/download"
    exit 1
fi

# Check if backend server is running
if ! lsof -i :8000 &> /dev/null; then
    echo -e "${YELLOW}⚠️  Backend server is not running on port 8000${NC}"
    echo "Please start your backend server first:"
    echo "  cd backend && python run.py"
    echo ""
    read -p "Press Enter to continue once backend is running, or Ctrl+C to exit..."
fi

echo -e "${GREEN}✅ Starting ngrok tunnel...${NC}"
echo ""

# Start ngrok
echo -e "${BLUE}📡 Running: ngrok http 8000${NC}"
echo ""
echo -e "${YELLOW}📋 Copy the HTTPS URL from ngrok and paste it in your iOS app settings:${NC}"
echo "   1. Open ZivoHealth app"
echo "   2. Go to Settings tab"
echo "   3. In 'API Configuration' section, select 'ngrok Tunnel'"
echo "   4. Paste the HTTPS URL (e.g., https://abc123.ngrok-free.app)"
echo "   5. Tap 'Update Endpoint'"
echo ""
echo -e "${GREEN}🎯 Your app will now connect to the backend via ngrok tunnel!${NC}"
echo ""
echo "Press Ctrl+C to stop ngrok tunnel"
echo ""

# Start ngrok
ngrok http 8000 