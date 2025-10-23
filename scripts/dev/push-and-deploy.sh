#!/usr/bin/env bash
set -euo pipefail

# Enable shell tracing when DEBUG=1
if [[ "${DEBUG:-0}" == "1" ]]; then
  set -x
fi

echo "🚀 Production Deploy: Push Images and Deploy to EC2"
echo "===================================================="

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
TF_DIR="$ROOT_DIR/infra/terraform"
REGION="us-east-1"
ENV_PROD_FILE="$ROOT_DIR/backend/.env.production"

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

echo ""
echo "🔐 Logging into ECR: $ECR_REGISTRY_HOST"
# Try to login to ECR (Mac keychain may fail, but docker can still work)
if ! aws_cmd ecr get-login-password | docker login --username AWS --password-stdin "$ECR_REGISTRY_HOST" 2>&1; then
  echo "⚠️  Warning: ECR login had keychain issues (error -50), but continuing..."
  echo "   Docker may still be able to push if already authenticated."
fi

echo ""
echo "📤 Pushing backend image to ECR..."
docker push "$ECR_REGISTRY_HOST/zivohealth-production-backend:$TAG"

echo ""
echo "📤 Pushing caddy image to ECR..."
docker push "$ECR_REGISTRY_HOST/zivohealth-production-caddy:$TAG"

echo ""
echo "📤 Pushing dashboard image to ECR..."
docker push "$ECR_REGISTRY_HOST/zivohealth-production-dashboard:$TAG"

echo ""
echo "✅ All images pushed successfully!"
echo ""
echo "☁️  Triggering EC2 to fetch compose from S3, verify checksum, pull & restart services..."

# Build remote script and send via SSM using base64 to avoid quoting issues
REMOTE_SCRIPT=$(cat <<'EOF'
set -eo pipefail
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

# Regenerate complete .env file from SSM (like user_data does)
echo "Regenerating complete .env file from SSM Parameter Store..."
cat > /tmp/regenerate_env.sh <<'ENVSCRIPT'
#!/bin/bash
# Note: No set -e to allow sed to continue if patterns don't exist

PROJECT="zivohealth"
ENVIRONMENT="production"
REGION="us-east-1"

# Fetch all SSM parameters (with fallback to .env.production defaults)
POSTGRES_SERVER=$(aws ssm get-parameter --name "/${PROJECT}/${ENVIRONMENT}/db/host" --query "Parameter.Value" --output text --region $REGION 2>/dev/null || echo "")
POSTGRES_USER=$(aws ssm get-parameter --name "/${PROJECT}/${ENVIRONMENT}/db/user" --query "Parameter.Value" --output text --region $REGION 2>/dev/null || echo "zivo")
POSTGRES_PASSWORD=$(aws ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/db/password" --query "Parameter.Value" --output text --region $REGION 2>/dev/null || echo "")
SECRET_KEY=$(aws ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/app/secret_key" --query "Parameter.Value" --output text --region $REGION 2>/dev/null || echo "zivohealth900")
VALID_API_KEYS=$(aws ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/api/valid_api_keys" --query "Parameter.Value" --output text --region $REGION 2>/dev/null || echo '["UMYpN67NeR0W13cP13O62Mn04yG3tpEx","D9PY5OWI2ouo48bqbnEAgRXe6AwUjgqj","KPUVJoBmITZujZecaOkudjg4OQuBq04M","6WQcXe0OKklL3yhJTMBp5bwJEYhKPjf9"]')
APP_SECRET_KEY=$(aws ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/app/app_secret_key" --query "Parameter.Value" --output text --region $REGION 2>/dev/null || echo "c7357b83f692134381cbd7cadcd34be9c6150121aa274599317b5a1283c0205f")
OPENAI_API_KEY=$(aws ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/openai/api_key" --query "Parameter.Value" --output text --region $REGION 2>/dev/null || echo "")
LANGCHAIN_API_KEY=$(aws ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/langchain/api_key" --query "Parameter.Value" --output text --region $REGION 2>/dev/null || echo "")
E2B_API_KEY=$(aws ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/e2b/api_key" --query "Parameter.Value" --output text --region $REGION 2>/dev/null || echo "")
SERPAPI_KEY=$(aws ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/serpapi/api_key" --query "Parameter.Value" --output text --region $REGION 2>/dev/null || echo "")
LIVEKIT_URL=$(aws ssm get-parameter --name "/${PROJECT}/${ENVIRONMENT}/livekit/url" --query "Parameter.Value" --output text --region $REGION 2>/dev/null || echo "ws://192.168.0.100:7880")
LIVEKIT_API_KEY=$(aws ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/livekit/api_key" --query "Parameter.Value" --output text --region $REGION 2>/dev/null || echo "devkey")
LIVEKIT_API_SECRET=$(aws ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/livekit/api_secret" --query "Parameter.Value" --output text --region $REGION 2>/dev/null || echo "devsecret")
REMINDER_FCM_PROJECT_ID=$(aws ssm get-parameter --name "/${PROJECT}/${ENVIRONMENT}/reminders/fcm_project_id" --query "Parameter.Value" --output text --region $REGION 2>/dev/null)
[ -z "$REMINDER_FCM_PROJECT_ID" ] && REMINDER_FCM_PROJECT_ID="test-zivo"

SMTP_PASSWORD=$(aws ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/smtp/password" --query "Parameter.Value" --output text --region $REGION 2>/dev/null || echo "")
# SMTP_PASSWORD fallback is in .env.production.base (uploaded from local)

REACT_APP_API_KEY=$(aws ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/react_app/api_key" --query "Parameter.Value" --output text --region $REGION 2>/dev/null || echo "")
# REACT_APP_API_KEY fallback is in .env.production.base (uploaded from local)

ML_WORKER_ENABLED=$(aws ssm get-parameter --name "/${PROJECT}/${ENVIRONMENT}/ml_worker/enabled" --query "Parameter.Value" --output text --region $REGION 2>/dev/null || echo "false")
ML_WORKER_SQS_QUEUE_URL=$(aws ssm get-parameter --name "/${PROJECT}/${ENVIRONMENT}/ml_worker/queue_url" --query "Parameter.Value" --output text --region $REGION 2>/dev/null || echo "")

echo "Debug: REMINDER_FCM_PROJECT_ID=$REMINDER_FCM_PROJECT_ID"
echo "Debug: REACT_APP_API_KEY=$REACT_APP_API_KEY"
echo "Debug: SMTP_PASSWORD=${SMTP_PASSWORD:0:5}**** (length: ${#SMTP_PASSWORD})"
echo "Debug: ML_WORKER_ENABLED=$ML_WORKER_ENABLED"
echo "Debug: ML_WORKER_SQS_QUEUE_URL=$ML_WORKER_SQS_QUEUE_URL"

# Check for FCM credentials
REMINDER_FCM_CREDENTIALS_JSON=$(aws ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/reminders/fcm_credentials_json" --query "Parameter.Value" --output text --region $REGION 2>/dev/null)

sudo mkdir -p /opt/zivohealth/keys
if [ -n "$REMINDER_FCM_CREDENTIALS_JSON" ] && [ "$REMINDER_FCM_CREDENTIALS_JSON" != "" ] && [ "$REMINDER_FCM_CREDENTIALS_JSON" != "None" ]; then
    echo "$REMINDER_FCM_CREDENTIALS_JSON" | sudo tee /opt/zivohealth/keys/fcm-credentials.json >/dev/null
    sudo chmod 600 /opt/zivohealth/keys/fcm-credentials.json
    FCM_CREDENTIALS_PATH="/opt/zivohealth/keys/fcm-credentials.json"
    echo "Debug: FCM credentials written to $FCM_CREDENTIALS_PATH"
else
    sudo rm -f /opt/zivohealth/keys/fcm-credentials.json
    FCM_CREDENTIALS_PATH=""
    echo "Debug: No FCM credentials found in SSM, using empty path"
fi

echo "Debug: FCM_CREDENTIALS_PATH=$FCM_CREDENTIALS_PATH"

# Create complete .env file (create as user first, then move with sudo to preserve variable expansion)
# Copy base .env.production file from /opt/zivohealth/.env.production.base (uploaded separately)
if [ -f /opt/zivohealth/.env.production.base ]; then
    cp /opt/zivohealth/.env.production.base /tmp/.env.new
else
    echo "ERROR: /opt/zivohealth/.env.production.base not found!"
    exit 1
fi

# Helper function to set or append environment variables
set_env_var() {
  local key="\$1"
  local value="\$2"
  if grep -q "^\${key}=" /tmp/.env.new 2>/dev/null; then
    sed -i "s|^\${key}=.*|\${key}=\${value}|g" /tmp/.env.new
  else
    echo "\${key}=\${value}" >> /tmp/.env.new
  fi
}

# Add/Override database configuration
set_env_var "POSTGRES_SERVER" "${POSTGRES_SERVER}"
set_env_var "POSTGRES_PORT" "5432"
set_env_var "POSTGRES_USER" "${POSTGRES_USER}"
set_env_var "POSTGRES_PASSWORD" "${POSTGRES_PASSWORD}"
set_env_var "POSTGRES_DB" "zivohealth_dev"

# Add/Override API keys and secrets
set_env_var "SECRET_KEY" "${SECRET_KEY}"
set_env_var "OPENAI_API_KEY" "\"${OPENAI_API_KEY}\""
set_env_var "LANGCHAIN_API_KEY" "\"${LANGCHAIN_API_KEY}\""
set_env_var "E2B_API_KEY" "\"${E2B_API_KEY}\""
set_env_var "SERPAPI_KEY" "\"${SERPAPI_KEY}\""
set_env_var "LIVEKIT_URL" "${LIVEKIT_URL}"
set_env_var "LIVEKIT_API_KEY" "${LIVEKIT_API_KEY}"
set_env_var "LIVEKIT_API_SECRET" "${LIVEKIT_API_SECRET}"
set_env_var "LIVEKIT_KEYS" "${LIVEKIT_API_KEY}:${LIVEKIT_API_SECRET}"
set_env_var "VALID_API_KEYS" "${VALID_API_KEYS}"
set_env_var "APP_SECRET_KEY" "${APP_SECRET_KEY}"
set_env_var "REACT_APP_SECRET_KEY" "${APP_SECRET_KEY}"

# Only override SMTP_PASSWORD if we got a value from SSM
if [ -n "${SMTP_PASSWORD}" ]; then
  set_env_var "SMTP_PASSWORD" "${SMTP_PASSWORD}"
fi

set_env_var "REMINDER_FCM_PROJECT_ID" "${REMINDER_FCM_PROJECT_ID}"
set_env_var "REACT_APP_API_KEY" "\"${REACT_APP_API_KEY}\""
set_env_var "REMINDER_FCM_CREDENTIALS_JSON" "${FCM_CREDENTIALS_PATH}"
set_env_var "GOOGLE_APPLICATION_CREDENTIALS" "${FCM_CREDENTIALS_PATH}"
set_env_var "ML_WORKER_ENABLED" "${ML_WORKER_ENABLED}"
set_env_var "ML_WORKER_SQS_QUEUE_URL" "${ML_WORKER_SQS_QUEUE_URL}"

# Enable LOINC mapper for lab processing
set_env_var "LOINC_ENABLED" "1"
set_env_var "LOINC_CREATE_TABLES" "0"

# Set ENVIRONMENT to production
set_env_var "ENVIRONMENT" "production"

# Remove or comment out separator lines that Docker can't parse
sed -i 's/^=\+$/# &/' /tmp/.env.new
sed -i 's/^-\+$/# &/' /tmp/.env.new

# Move the file to the final location with sudo
sudo mv /tmp/.env.new /opt/zivohealth/.env
sudo chown root:root /opt/zivohealth/.env
sudo chmod 644 /opt/zivohealth/.env

# Verify the file was created
if [ -f /opt/zivohealth/.env ]; then
    echo "✅ Complete .env file regenerated from SSM!"
    echo "   - POSTGRES_SERVER: $POSTGRES_SERVER"
    echo "   - POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:0:4}****"
    echo "   - OPENAI_API_KEY: ${OPENAI_API_KEY:0:10}****"
    echo "   - REACT_APP_API_KEY: ${REACT_APP_API_KEY:0:10}****"
else
    echo "❌ ERROR: Failed to create .env file!"
    exit 1
fi
ENVSCRIPT

# Run the regeneration script
echo "Running .env regeneration script..."
if sudo bash /tmp/regenerate_env.sh 2>&1; then
    echo "✅ .env regeneration completed successfully"
else
    echo "❌ WARNING: .env regeneration had errors, but continuing..."
fi
sudo rm -f /tmp/regenerate_env.sh

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

# Setup Fail2Ban for API protection (idempotent)
echo "Configuring Fail2Ban for API protection..."
if ! command -v fail2ban-client &> /dev/null; then
  echo "Installing fail2ban..."
  sudo apt-get update -y
  sudo apt-get install -y fail2ban
fi

# Create custom filter for API attacks
sudo tee /etc/fail2ban/filter.d/api-env-scan.conf > /dev/null <<'F2BFILTER'
[Definition]
# Detect attempts to access sensitive files
failregex = ^.*"(HEAD|GET|POST) /\.env[^"]*" 401.*$
            ^.*"(HEAD|GET|POST) /\.git[^"]*" 401.*$
            ^.*"(HEAD|GET|POST) /config\.json[^"]*" 401.*$
            ^.*"(HEAD|GET|POST) /\.aws[^"]*" 401.*$
            ^.*"(HEAD|GET|POST) /credentials[^"]*" 401.*$
            ^.*"(HEAD|GET|POST) /secrets[^"]*" 401.*$

ignoreregex =
F2BFILTER

# Create jail configuration
sudo tee /etc/fail2ban/jail.d/api-protection.conf > /dev/null <<'F2BJAIL'
[api-env-scan]
enabled = true
port = http,https
filter = api-env-scan
logpath = /var/log/docker/zivohealth-api.log
maxretry = 5
findtime = 300
bantime = 3600
action = iptables-multiport[name=API-ATTACK, port="http,https"]
F2BJAIL

# Create directory for docker logs
sudo mkdir -p /var/log/docker

# Create docker log monitoring script
sudo tee /usr/local/bin/monitor-docker-logs.sh > /dev/null <<'F2BLOGMON'
#!/bin/bash
LOG_FILE="/var/log/docker/zivohealth-api.log"
touch "$LOG_FILE"
docker logs -f zivohealth-api 2>&1 | while read line; do
    echo "$(date '+%Y-%m-%d %H:%M:%S') $line" >> "$LOG_FILE"
done
F2BLOGMON

sudo chmod +x /usr/local/bin/monitor-docker-logs.sh

# Create systemd service for log monitoring
sudo tee /etc/systemd/system/docker-api-logs.service > /dev/null <<'F2BSVC'
[Unit]
Description=Docker API Log Monitoring for Fail2Ban
After=docker.service
Requires=docker.service

[Service]
Type=simple
ExecStart=/usr/local/bin/monitor-docker-logs.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
F2BSVC

# Enable and (re)start services
sudo systemctl daemon-reload
sudo systemctl enable fail2ban
sudo systemctl enable docker-api-logs.service
sudo systemctl restart fail2ban
sudo systemctl restart docker-api-logs.service

echo "✅ Fail2Ban configured and active!"
echo "   Status: $(sudo systemctl is-active fail2ban)"
echo "   Jail status: $(sudo fail2ban-client status api-env-scan 2>/dev/null | grep -c 'api-env-scan' || echo 'initializing...')"

echo "Waiting for health checks to pass..."
sleep 30
docker compose ps
EOF
)

# Upload .env.production file to EC2 first
echo "📤 Uploading .env.production base file to EC2..."
ENV_PROD_CONTENT=$(cat "$ENV_PROD_FILE" | base64)
aws_cmd ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters commands="[\"echo '$ENV_PROD_CONTENT' | base64 -d | sudo tee /opt/zivohealth/.env.production.base >/dev/null && sudo chmod 644 /opt/zivohealth/.env.production.base && echo 'Base .env uploaded'\"]" \
  --query "Command.CommandId" --output text >/dev/null
sleep 3
echo "✅ Base .env.production uploaded"

REMOTE_B64=$(printf "%s" "$REMOTE_SCRIPT" | base64)

CMD_ID=$(aws_cmd ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters commands="[\"bash -c \\\"echo '$REMOTE_B64' | base64 -d > /tmp/deploy.sh && chmod +x /tmp/deploy.sh && REGION='$REGION' S3_BUCKET='$S3_BUCKET' S3_KEY='$S3_KEY' COMPOSE_SSM_KEY='$COMPOSE_SSM_KEY' ECR_REGISTRY_HOST='$ECR_REGISTRY_HOST' bash /tmp/deploy.sh\\\"\"]" \
  --query "Command.CommandId" --output text)

echo "⌛ Waiting for SSM command to complete..."
echo "  CommandId: $CMD_ID"
# Give SSM a moment to dispatch
sleep 3
# Poll for completion up to ~5 minutes (allowing more time for docker pull)
for i in $(seq 1 60); do
  STATUS=$(aws_cmd ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" --query 'Status' --output text 2>/dev/null || echo "Unknown")
  DETAILS=$(aws_cmd ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" --query 'StatusDetails' --output text 2>/dev/null || true)
  STDOUT_URL=$(aws_cmd ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" --query 'StandardOutputUrl' --output text 2>/dev/null || true)
  STDERR_URL=$(aws_cmd ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" --query 'StandardErrorUrl' --output text 2>/dev/null || true)
  echo "  [$i/60] Status=$STATUS Details=$DETAILS StdoutURL=${STDOUT_URL:-none} StderrURL=${STDERR_URL:-none}"
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

echo ""
echo "✅ Deploy complete! Use this to check status any time:"
echo "aws --profile $AWS_PROFILE --region $REGION ssm send-command --instance-ids $INSTANCE_ID --document-name AWS-RunShellScript --parameters 'commands=[\"cd /opt/zivohealth\",\"docker compose ps\",\"docker ps --format \\\"table {{.Names}}\\t{{.Status}}\\t{{.Ports}}\\\"\"]'"

