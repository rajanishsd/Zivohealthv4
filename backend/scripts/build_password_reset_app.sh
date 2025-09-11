#!/bin/bash

# Build script for password reset React app
set -e

echo "🔨 Building ZivoHealth Password Reset App..."

# Navigate to the password reset app directory
cd "$(dirname "$0")/../password-reset-app"

# Check if node_modules exists, if not install dependencies
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Build the app
echo "🏗️ Building React app..."
npm run build

# Create reset-password directory in www if it doesn't exist
echo "📁 Preparing deployment directory..."
mkdir -p ../www/reset-password

# Copy build files to www directory
echo "📋 Copying build files..."
cp -r build/* ../www/reset-password/

echo "✅ Password reset app built and deployed successfully!"
echo "📍 Reset page available at: https://zivohealth.ai/reset-password"
echo ""
echo "Next steps:"
echo "1. Configure email settings in your .env file"
echo "2. Run database migration: alembic upgrade head"
echo "3. Restart your backend server"
