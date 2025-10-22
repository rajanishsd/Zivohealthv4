#!/usr/bin/env bash
set -euo pipefail

# Build and Push Base Image to ECR
# This script should be run RARELY - only when ML dependencies change
# (torch, transformers, sentence-transformers, etc.)

# Enable shell tracing when DEBUG=1
if [[ "${DEBUG:-0}" == "1" ]]; then
  set -x
fi

echo "🏗️  Building Base Image with ML Dependencies"
echo "=============================================="
echo "⚠️  WARNING: This build takes 10-15 minutes!"
echo "⚠️  Only run this when requirements-base.txt changes"
echo ""

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
BASE_IMAGE_TAG="${1:-latest}"

if [[ -z "$ECR_REGISTRY_HOST" ]]; then
  echo "❌ Could not read Terraform outputs. Ensure terraform apply completed."
  exit 1
fi

echo "📦 Variables:"
echo "  ECR_REGISTRY_HOST  = $ECR_REGISTRY_HOST"
echo "  BASE_IMAGE_TAG     = $BASE_IMAGE_TAG"
echo "  REGION             = $REGION"
echo ""

# Login to ECR
echo "🔐 Logging into ECR..."
aws_cmd ecr get-login-password | docker login --username AWS --password-stdin "$ECR_REGISTRY_HOST"

# Create ECR repository if it doesn't exist
echo ""
echo "📦 Ensuring ECR repository 'zivohealth-base' exists..."
if ! aws_cmd ecr describe-repositories --repository-names zivohealth-base >/dev/null 2>&1; then
  echo "   Creating ECR repository 'zivohealth-base'..."
  aws_cmd ecr create-repository \
    --repository-name zivohealth-base \
    --image-scanning-configuration scanOnPush=true \
    --encryption-configuration encryptionType=AES256
  echo "   ✅ ECR repository created!"
else
  echo "   ✅ ECR repository already exists!"
fi

echo ""
echo "🧱 Ensuring docker buildx builder exists..."
docker buildx ls >/dev/null 2>&1 || docker buildx create --use --name zivo-builder >/dev/null 2>&1 || true
docker buildx use zivo-builder

echo ""
echo "🐳 Building base image (linux/amd64) with ML dependencies..."
echo "   This includes: torch, transformers, sentence-transformers"
echo "   Expected build time: 10-15 minutes"
echo ""

# Build the base image
docker buildx build --platform linux/amd64 \
  -f "$ROOT_DIR/backend/Dockerfile.base" \
  -t "zivohealth-base:$BASE_IMAGE_TAG" \
  -t "$ECR_REGISTRY_HOST/zivohealth-base:$BASE_IMAGE_TAG" \
  "$ROOT_DIR/backend" \
  --load

echo ""
echo "✅ Base image built successfully!"
echo ""

# Show image size
echo "📊 Image details:"
docker images | grep "zivohealth-base" | head -3

echo ""
echo "🚀 Pushing base image to ECR..."
docker push "$ECR_REGISTRY_HOST/zivohealth-base:$BASE_IMAGE_TAG"

echo ""
echo "✅ Base image pushed to ECR successfully!"
echo ""
echo "📝 Base image URI: $ECR_REGISTRY_HOST/zivohealth-base:$BASE_IMAGE_TAG"
echo ""
echo "💡 Next steps:"
echo "   1. This base image is now available in ECR"
echo "   2. The application image will automatically use this base"
echo "   3. Run ./scripts/dev/build-production-images.sh to build the app image"
echo ""

