#!/bin/bash
set -e

# Configuration
AWS_REGION="us-east-1"
ECR_REPO_URL="474221740916.dkr.ecr.us-east-1.amazonaws.com"
IMAGE_TAG="latest"

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REPO_URL

# Build and push Caddy image
echo "Building Caddy image..."
docker build -f Dockerfile.caddy -t $ECR_REPO_URL/zivohealth-dev-caddy:$IMAGE_TAG .
docker push $ECR_REPO_URL/zivohealth-dev-caddy:$IMAGE_TAG

# Build and push Dashboard image
echo "Building Dashboard image..."
cd ../../../../backend

# Get the secret key and API key from environment or backend config
echo "🔍 Getting configuration from backend..."

# Try to get SECRET_KEY from environment first, then from backend config
if [ -n "$REACT_APP_SECRET_KEY" ]; then
    SECRET_KEY="$REACT_APP_SECRET_KEY"
    echo "✅ Using SECRET_KEY from environment variable"
else
    echo "🔍 Extracting SECRET_KEY from backend configuration..."
    SECRET_KEY=$(cd ../../../../backend && python3 -c "
import sys
import os
sys.path.insert(0, '.')
try:
    from app.core.config import settings
    print(settings.SECRET_KEY)
except Exception as e:
    print('Error:', e, file=sys.stderr)
    print('')
" 2>/dev/null || echo "")
fi

# Try to get API_KEY from environment first, then from backend config
if [ -n "$REACT_APP_API_KEY" ]; then
    API_KEY="$REACT_APP_API_KEY"
    echo "✅ Using API_KEY from environment variable"
else
    echo "🔍 Extracting API_KEY from backend configuration..."
    API_KEY=$(cd ../../../../backend && python3 -c "
import sys
import os
sys.path.insert(0, '.')
try:
    from app.core.config import settings
    if settings.VALID_API_KEYS:
        print(settings.VALID_API_KEYS[0])
    else:
        print('')
except Exception as e:
    print('Error:', e, file=sys.stderr)
    print('')
" 2>/dev/null || echo "")
fi

# Check if we got the values
if [ -z "$SECRET_KEY" ]; then
    echo "❌ Error: Could not get SECRET_KEY"
    echo "💡 Set REACT_APP_SECRET_KEY environment variable or ensure backend config is accessible"
    exit 1
fi

if [ -z "$API_KEY" ]; then
    echo "❌ Error: Could not get API_KEY"
    echo "💡 Set REACT_APP_API_KEY environment variable or ensure backend config is accessible"
    exit 1
fi

echo "🔑 Using SECRET_KEY: ${SECRET_KEY:0:8}...${SECRET_KEY: -4} (length: ${#SECRET_KEY})"
echo "🔑 Using API_KEY: ${API_KEY:0:8}...${API_KEY: -4} (length: ${#API_KEY})"

docker build -f Dockerfile.dashboard \
  --build-arg REACT_APP_SECRET_KEY="$SECRET_KEY" \
  --build-arg REACT_APP_API_KEY="$API_KEY" \
  -t $ECR_REPO_URL/zivohealth-dev-dashboard:$IMAGE_TAG .
docker push $ECR_REPO_URL/zivohealth-dev-dashboard:$IMAGE_TAG

echo "All images built and pushed successfully!"
