#!/usr/bin/env bash
set -euo pipefail

# Complete production deployment workflow
# 1. Set production environment
# 2. Build and push Docker image to ECR (React app builds inside Docker)
# 3. Deploy to EC2

echo "🚀 Starting Production Deployment Workflow"
echo "=========================================="

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"

# Step 1: Set production environment
echo ""
echo "📋 Step 1: Setting up production environment configuration..."
cd "$BACKEND_DIR"

if [ -f ".env.production" ]; then
    cp .env.production .env
    echo "✅ Production environment configuration activated"
else
    echo "❌ Error: .env.production file not found"
    echo "   Please create backend/.env.production with production configuration"
    exit 1
fi

# Step 2: Build and push Docker image (React app builds inside Docker)
echo ""
echo "🐳 Step 2: Building and pushing Docker image to ECR..."
cd "$ROOT_DIR"

if [ -f "scripts/dev/build_ecr_backend.sh" ]; then
    ./scripts/dev/build_ecr_backend.sh
    echo "✅ Docker image built and pushed to ECR"
else
    echo "❌ Error: build_ecr_backend.sh script not found"
    exit 1
fi

# Step 3: Deploy to EC2
echo ""
echo "☁️  Step 3: Deploying to EC2..."
if [ -f "scripts/dev/deploy_compose_on_ec2.sh" ]; then
    ./scripts/dev/deploy_compose_on_ec2.sh
    echo "✅ Deployment to EC2 completed"
else
    echo "❌ Error: deploy_compose_on_ec2.sh script not found"
    exit 1
fi

echo ""
echo "🎉 Production deployment workflow completed successfully!"
echo ""
echo "📊 Summary:"
echo "  • Environment: Production configuration activated"
echo "  • React App: Built inside Docker image during build process"
echo "  • Docker Image: Built and pushed to ECR"
echo "  • EC2 Deployment: Completed"
echo ""
echo "🌐 Your production application should now be running on EC2"
