#!/usr/bin/env bash
set -euo pipefail

# Enable shell tracing when DEBUG=1
if [[ "${DEBUG:-0}" == "1" ]]; then
  set -x
fi

# Production deploy: Build images locally, then push and deploy to EC2
# This script calls two separate scripts to allow retrying push/deploy without rebuilding

echo "🚀 Production Deploy: Build, Push, and Deploy"
echo "=============================================="
echo ""
echo "This script runs two steps:"
echo "  1. Build images locally (./build-production-images.sh)"
echo "  2. Push to ECR and deploy to EC2 (./push-and-deploy.sh)"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Step 1: Build images locally
echo "Step 1: Building images..."
"$SCRIPT_DIR/build-production-images.sh"

echo ""
echo "✅ Build complete!"
echo ""

# Step 2: Push and deploy
echo "Step 2: Pushing and deploying..."
"$SCRIPT_DIR/push-and-deploy.sh"

exit 0

# Original combined script below (kept for reference but not executed)
exit 0

ROOT_DIR_UNUSED="$(cd "$(dirname "$0")/../.." && pwd)"
TF_DIR="$ROOT_DIR/infra/terraform"
REGION="us-east-1"

: "${AWS_PROFILE:=zivohealth}"

# Helper to run aws with the selected profile and region
aws_cmd() { aws --profile "$AWS_PROFILE" --region "$REGION" "$@"; }

echo "🔧 Validating Terraform outputs (instance id, ECR registry)..."
cd "$TF_DIR"
INSTANCE_ID=$(terraform output -raw ec2_instance_id)
ECR_BACKEND_URL=$(terraform output -raw ecr_repository_url)
ECR_REGISTRY_HOST=${ECR_BACKEND_URL%%/*}
S3_BUCKET=$(aws_cmd ssm get-parameter --name "/zivohealth/production/s3/bucket" --query "Parameter.Value" --output text || echo "zivohealth-data")
S3_KEY="deploy/production/docker-compose.yml"
COMPOSE_SSM_KEY="/zivohealth/production/deploy/docker_compose_sha256"
TAG="latest"

if [[ -z "$INSTANCE_ID" || -z "$ECR_REGISTRY_HOST" ]]; then
  echo "❌ Could not read Terraform outputs. Ensure Step 1 (terraform apply) completed."
  exit 1
fi

echo "📦 Variables:"
echo "  INSTANCE_ID        = $INSTANCE_ID"
echo "  ECR_REGISTRY_HOST  = $ECR_REGISTRY_HOST"
echo "  S3_BUCKET          = $S3_BUCKET"
echo "  S3_KEY             = $S3_KEY"
echo "  COMPOSE_SSM_KEY    = $COMPOSE_SSM_KEY"
echo "  REGION             = $REGION"

echo "🧱 Ensuring docker buildx builder exists..."
docker buildx ls >/dev/null 2>&1 || docker buildx create --use >/dev/null 2>&1 || true

echo "🔐 Logging into ECR: $ECR_REGISTRY_HOST"
aws_cmd ecr get-login-password | docker login --username AWS --password-stdin "$ECR_REGISTRY_HOST"

echo "🐳 Building and pushing backend image (linux/amd64)..."
docker buildx build --platform linux/amd64 -t "$ECR_REGISTRY_HOST/zivohealth-production-backend:$TAG" "$ROOT_DIR/backend" --push

echo "🐳 Building and pushing caddy image (linux/amd64)..."
docker buildx build --platform linux/amd64 \
  -f "$ROOT_DIR/infra/terraform/modules/compute/Dockerfile.caddy" \
  -t "$ECR_REGISTRY_HOST/zivohealth-production-caddy:$TAG" \
  "$ROOT_DIR/infra/terraform/modules/compute" \
  --push

echo "🐳 Building and pushing dashboard image (linux/amd64)..."

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
  --push

echo "☁️  Triggering EC2 to fetch compose from S3, verify checksum, pull & restart services..."

# Build remote script and send via SSM using base64 to avoid quoting issues
REMOTE_SCRIPT=$(cat <<'EOF'
set -eo pipefail
set -x
export AWS_DEFAULT_REGION="$REGION"
# Use instance role by clearing any local/stale creds
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_PROFILE || true

cd /opt/zivohealth
# Ensure AWS env values and S3 upload settings in /opt/zivohealth/.env (no static access keys)
if [ -f .env ]; then
  sudo sed -i.bak \
    -e "s/^AWS_DEFAULT_REGION=.*/AWS_DEFAULT_REGION=$REGION/" \
    -e "s/^AWS_REGION=.*/AWS_REGION=$REGION/" \
    -e "s/^AWS_S3_BUCKET=.*/AWS_S3_BUCKET=zivohealth-data/" \
    -e "s/^USE_S3_UPLOADS=.*/USE_S3_UPLOADS=true/" \
    -e "s|^UPLOADS_S3_PREFIX=.*|UPLOADS_S3_PREFIX=uploads/chat|" .env || true
  grep -q '^AWS_DEFAULT_REGION=' .env || echo "AWS_DEFAULT_REGION=$REGION" | sudo tee -a .env >/dev/null
  grep -q '^AWS_REGION=' .env || echo "AWS_REGION=$REGION" | sudo tee -a .env >/dev/null
  grep -q '^AWS_S3_BUCKET=' .env || echo "AWS_S3_BUCKET=zivohealth-data" | sudo tee -a .env >/dev/null
  grep -q '^USE_S3_UPLOADS=' .env || echo "USE_S3_UPLOADS=true" | sudo tee -a .env >/dev/null
  grep -q '^UPLOADS_S3_PREFIX=' .env || echo "UPLOADS_S3_PREFIX=uploads/chat" | sudo tee -a .env >/dev/null

  # Fetch and set AI-related API keys from SSM (quoted)
  LANG_SSM="/zivohealth/production/langchain/api_key"
  SERP_SSM="/zivohealth/production/serpapi/api_key"
  LANG=$(aws ssm get-parameter --with-decryption --name "$LANG_SSM" --query 'Parameter.Value' --output text --region $REGION 2>/dev/null || true)
  SERP=$(aws ssm get-parameter --with-decryption --name "$SERP_SSM" --query 'Parameter.Value' --output text --region $REGION 2>/dev/null || true)

  if [ -n "$LANG" ] && [ "$LANG" != "None" ]; then
    if grep -q '^LANGCHAIN_API_KEY=' .env; then
      sudo sed -i "s|^LANGCHAIN_API_KEY=.*|LANGCHAIN_API_KEY=\"$LANG\"|" .env
    else
      echo "LANGCHAIN_API_KEY=\"$LANG\"" | sudo tee -a .env >/dev/null
    fi
  fi
  if [ -n "$SERP" ] && [ "$SERP" != "None" ]; then
    if grep -q '^SERPAPI_KEY=' .env; then
      sudo sed -i "s|^SERPAPI_KEY=.*|SERPAPI_KEY=\"$SERP\"|" .env
    else
      echo "SERPAPI_KEY=\"$SERP\"" | sudo tee -a .env >/dev/null
    fi
  fi
fi

echo "Fetching compose from s3://$S3_BUCKET/$S3_KEY ..."
aws s3 cp s3://$S3_BUCKET/$S3_KEY docker-compose.yml.tmp --region "$REGION"
test -s docker-compose.yml.tmp
DOWN=$(sha256sum docker-compose.yml.tmp | cut -d' ' -f1)
EXP=$(aws ssm get-parameter --name $COMPOSE_SSM_KEY --region "$REGION" --query 'Parameter.Value' --output text)
echo "Expected: \"$EXP\" | Got: \"$DOWN\""
test "$DOWN" = "$EXP"
echo "Validating compose..."
docker compose -f docker-compose.yml.tmp config >/dev/null
echo "Applying..."
( flock 9; mv docker-compose.yml.tmp docker-compose.yml ) 9>.compose.lock
echo "Logging into ECR..."
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin $ECR_REGISTRY_HOST
echo "Pulling images..."
docker compose pull
echo "Stopping all services..."
docker compose down
echo "Starting services with latest images..."
docker compose up -d
echo "Waiting for services to start..."
sleep 10
echo "Checking service health..."
docker compose ps
echo "Waiting for health checks to pass..."
sleep 30
docker compose ps
EOF
 )

REMOTE_B64=$(printf "%s" "$REMOTE_SCRIPT" | base64)

CMD_ID=$(aws_cmd ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["bash","-lc","echo '"$REMOTE_B64"' | base64 -d > /tmp/deploy.sh && chmod +x /tmp/deploy.sh && REGION='"'"$REGION"'"' S3_BUCKET='"'"$S3_BUCKET"'"' S3_KEY='"'"$S3_KEY"'"' COMPOSE_SSM_KEY='"'"$COMPOSE_SSM_KEY"'"' ECR_REGISTRY_HOST='"'"$ECR_REGISTRY_HOST"'"' bash /tmp/deploy.sh"]' \
  --query "Command.CommandId" --output text)

echo "⌛ Waiting for SSM command to complete..."
echo "  CommandId: $CMD_ID"
# Give SSM a moment to dispatch
sleep 3
# Poll for completion up to ~2 minutes
for i in $(seq 1 24); do
  STATUS=$(aws_cmd ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" --query 'Status' --output text 2>/dev/null || echo "Unknown")
  DETAILS=$(aws_cmd ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" --query 'StatusDetails' --output text 2>/dev/null || true)
  STDOUT_URL=$(aws_cmd ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" --query 'StandardOutputUrl' --output text 2>/dev/null || true)
  STDERR_URL=$(aws_cmd ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" --query 'StandardErrorUrl' --output text 2>/dev/null || true)
  echo "  [$i/24] Status=$STATUS Details=$DETAILS StdoutURL=${STDOUT_URL:-none} StderrURL=${STDERR_URL:-none}"
  case "$STATUS" in
    Success)
      break
      ;;
    Failed|Cancelled|TimedOut|Undeliverable)
      echo "❌ SSM command ended with status: $STATUS ($DETAILS)"
      echo "  Hint: Undeliverable often means SSM agent is not running or instance role lacks permissions."
      aws_cmd ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" || true
      exit 1
      ;;
    *)
      sleep 5
      ;;
  esac
done

# Final invocation details and logs
echo "----- SSM Invocation Summary -----"
aws_cmd ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" || true
echo "----- SSM StandardOutputContent -----"
aws_cmd ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" --query 'StandardOutputContent' --output text || true
echo "----- SSM StandardErrorContent -----"
aws_cmd ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" --query 'StandardErrorContent' --output text || true

echo "✅ Deploy step complete. Use this to re-check status any time:"
echo "aws --profile $AWS_PROFILE --region $REGION ssm send-command --instance-ids $INSTANCE_ID --document-name AWS-RunShellScript --parameters commands='[\"cd /opt/zivohealth\",\"docker compose ps\",\"docker ps --format \"table {{.Names}}\\t{{.Status}}\\t{{.Ports}}\"\"]'"
