#!/usr/bin/env bash
set -euo pipefail

# Build Lightweight API Images
# API image is now lightweight (~500MB) - no ML dependencies needed
# ML workloads are handled by separate Fargate ML Worker
# Expected build time: 2-3 minutes

# Enable shell tracing when DEBUG=1
if [[ "${DEBUG:-0}" == "1" ]]; then
  set -x
fi

echo "🔨 Production Build: Building Lightweight Docker Images"
echo "========================================================="

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
TF_DIR="$ROOT_DIR/infra/terraform"
REGION="us-east-1"

: "${AWS_PROFILE:=zivohealth}"

# Helper to run aws with the selected profile and region
aws_cmd() { aws --profile "$AWS_PROFILE" --region "$REGION" "$@"; }

echo "🔧 Validating Terraform outputs (ECR registry)..."
cd "$TF_DIR"
ECR_BACKEND_URL=$(terraform output -raw ecr_repository_url)
ECR_REGISTRY_HOST=${ECR_BACKEND_URL%%/*}
TAG="latest"

if [[ -z "$ECR_REGISTRY_HOST" ]]; then
  echo "❌ Could not read Terraform outputs. Ensure terraform apply completed."
  exit 1
fi

echo "📦 Variables:"
echo "  ECR_REGISTRY_HOST  = $ECR_REGISTRY_HOST"
echo "  TAG                = $TAG"
echo "  REGION             = $REGION"

# Login to ECR
echo ""
echo "🔐 Logging into ECR..."
aws_cmd ecr get-login-password | docker login --username AWS --password-stdin "$ECR_REGISTRY_HOST"

echo ""
echo "🧱 Ensuring docker buildx builder exists..."
docker buildx ls >/dev/null 2>&1 || docker buildx create --use --name zivo-builder >/dev/null 2>&1 || true
docker buildx use zivo-builder

echo ""
echo "🐳 Building lightweight backend API image (linux/amd64)..."
echo "   No ML dependencies - API uses OpenAI API calls only"
echo "   Expected size: ~500MB (vs 4.6GB with ML)"
docker buildx build --platform linux/amd64 \
  -t "$ECR_REGISTRY_HOST/zivohealth-production-backend:$TAG" \
  "$ROOT_DIR/backend" \
  --load

echo ""
echo "🐳 Building caddy image (linux/amd64)..."
docker buildx build --platform linux/amd64 \
  -f "$ROOT_DIR/infra/terraform/modules/compute/Dockerfile.caddy" \
  -t "$ECR_REGISTRY_HOST/zivohealth-production-caddy:$TAG" \
  "$ROOT_DIR/infra/terraform/modules/compute" \
  --load

echo ""
echo "🐳 Building dashboard image (linux/amd64)..."

# Get the React environment variables from .env.production file
echo "🔍 Reading React environment variables from .env.production file..."

# Check if .env.production file exists
if [ ! -f "$ROOT_DIR/backend/.env.production" ]; then
    echo "❌ Error: .env.production file not found at $ROOT_DIR/backend/.env.production"
    echo "💡 Create a .env.production file in the backend directory with REACT_APP_SECRET_KEY and REACT_APP_API_KEY"
    exit 1
fi

# Extract only the React environment variables from the file
REACT_APP_SECRET_KEY=$(grep "^REACT_APP_SECRET_KEY=" "$ROOT_DIR/backend/.env.production" | cut -d'=' -f2- | tr -d '"')
REACT_APP_API_KEY=$(grep "^REACT_APP_API_KEY=" "$ROOT_DIR/backend/.env.production" | cut -d'=' -f2- | tr -d '"')

# Check if required variables are set
if [ -z "${REACT_APP_SECRET_KEY:-}" ]; then
    echo "❌ Error: REACT_APP_SECRET_KEY not found in .env.production file"
    exit 1
fi

if [ -z "${REACT_APP_API_KEY:-}" ]; then
    echo "❌ Error: REACT_APP_API_KEY not found in .env.production file"
    exit 1
fi

echo "✅ Using REACT_APP_SECRET_KEY from .env.production: ${REACT_APP_SECRET_KEY:0:8}...${REACT_APP_SECRET_KEY: -4} (length: ${#REACT_APP_SECRET_KEY})"
echo "✅ Using REACT_APP_API_KEY from .env.production: ${REACT_APP_API_KEY:0:8}...${REACT_APP_API_KEY: -4} (length: ${#REACT_APP_API_KEY})"

docker buildx build --platform linux/amd64 \
  -f "$ROOT_DIR/backend/Dockerfile.dashboard" \
  --build-arg REACT_APP_SECRET_KEY="$REACT_APP_SECRET_KEY" \
  --build-arg REACT_APP_API_KEY="$REACT_APP_API_KEY" \
  -t "$ECR_REGISTRY_HOST/zivohealth-production-dashboard:$TAG" \
  "$ROOT_DIR/backend" \
  --load

echo ""
echo "✅ All images built successfully!"
echo ""
echo "📊 Built images:"
docker images | grep "zivohealth-production" | head -10

echo ""
echo "💡 Image optimization:"
echo "   Backend API: ~500MB (lightweight - no ML dependencies)"
echo "   Caddy: ~50MB"
echo "   Dashboard: ~200MB"
echo "   Total: ~750MB (vs 4.6GB before!)"
echo ""
echo "📝 Next step: Run ./scripts/dev/push-and-deploy.sh to push images and deploy"

