#!/bin/bash
set -e

export AWS_DEFAULT_REGION=${AWS_REGION}

# Install updates and awscli
apt-get update -y || true
apt-get install -y ca-certificates curl gnupg lsb-release awscli || true

# CRITICAL: Remove snapd and install traditional SSM agent
echo "Removing snapd and installing traditional SSM agent..."

# Stop and disable snapd services
systemctl stop snapd || true
systemctl disable snapd || true
systemctl stop snapd.socket || true
systemctl disable snapd.socket || true
systemctl stop snapd.seeded || true
systemctl disable snapd.seeded || true

# Remove snap packages
snap remove amazon-ssm-agent || true
snap remove core20 || true
snap remove core22 || true
snap remove lxd || true
snap remove snapd || true

# Remove snapd package and clean up
apt-get remove --purge -y snapd || true
apt-get autoremove -y || true
apt-get autoclean || true

# Clean up snap directories
rm -rf /var/lib/snapd || true
rm -rf /snap || true
rm -rf /home/*/snap || true

# Install traditional SSM agent from AWS
echo "Installing traditional SSM agent..."
wget -q https://s3.amazonaws.com/ec2-downloads-windows/SSMAgent/latest/debian_amd64/amazon-ssm-agent.deb
dpkg -i amazon-ssm-agent.deb || true
rm amazon-ssm-agent.deb

# Enable and start traditional SSM agent
systemctl enable amazon-ssm-agent
systemctl start amazon-ssm-agent

# Verify SSM agent is running
systemctl status amazon-ssm-agent --no-pager || true

echo "Snapd removed and traditional SSM agent installed successfully!"

# Install Docker if not present
if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

usermod -aG docker ubuntu || true

# Install and configure Fail2Ban for API protection
echo "Setting up Fail2Ban to protect against API attacks..."
apt-get install -y fail2ban || true

# Create custom filter for API env file scanning attacks
cat > /etc/fail2ban/filter.d/api-env-scan.conf <<'EOF'
[Definition]
# Detect attempts to access sensitive files
failregex = ^.*"(HEAD|GET|POST) /\.env[^"]*" 401.*$
            ^.*"(HEAD|GET|POST) /\.git[^"]*" 401.*$
            ^.*"(HEAD|GET|POST) /config\.json[^"]*" 401.*$
            ^.*"(HEAD|GET|POST) /\.aws[^"]*" 401.*$
            ^.*"(HEAD|GET|POST) /credentials[^"]*" 401.*$
            ^.*"(HEAD|GET|POST) /secrets[^"]*" 401.*$

ignoreregex =
EOF

# Create jail configuration
cat > /etc/fail2ban/jail.d/api-protection.conf <<'EOF'
[api-env-scan]
enabled = true
port = http,https
filter = api-env-scan
logpath = /var/log/docker/zivohealth-api.log
maxretry = 5
findtime = 300
bantime = 3600
action = iptables-multiport[name=API-ATTACK, port="http,https"]
EOF

# Create directory for docker logs
mkdir -p /var/log/docker

# Create docker log monitoring script
cat > /usr/local/bin/monitor-docker-logs.sh <<'EOF'
#!/bin/bash
LOG_FILE="/var/log/docker/zivohealth-api.log"
touch "$LOG_FILE"
docker logs -f zivohealth-api 2>&1 | while read line; do
    echo "$(date '+%Y-%m-%d %H:%M:%S') $line" >> "$LOG_FILE"
done
EOF

chmod +x /usr/local/bin/monitor-docker-logs.sh

# Create systemd service for log monitoring
cat > /etc/systemd/system/docker-api-logs.service <<'EOF'
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
EOF

# Enable fail2ban and log monitoring (will start after docker is up)
systemctl enable fail2ban
systemctl enable docker-api-logs.service

echo "Fail2Ban configured successfully!"

# Create application directory
mkdir -p /opt/zivohealth
cd /opt/zivohealth

# Login to ECR
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REPO_URL}

# Get all configuration from SSM parameters
POSTGRES_SERVER=$(aws --region ${AWS_REGION} ssm get-parameter --name "/${PROJECT}/${ENVIRONMENT}/db/host" --query "Parameter.Value" --output text 2>/dev/null || echo "localhost")
POSTGRES_USER=$(aws --region ${AWS_REGION} ssm get-parameter --name "/${PROJECT}/${ENVIRONMENT}/db/user" --query "Parameter.Value" --output text 2>/dev/null || echo "zivo")
POSTGRES_PASSWORD=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/db/password" --query "Parameter.Value" --output text 2>/dev/null || echo "changeme")
SECRET_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/app/secret_key" --query "Parameter.Value" --output text 2>/dev/null || echo "zivohealth900")
VALID_API_KEYS=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/api/valid_api_keys" --query "Parameter.Value" --output text 2>/dev/null || echo "[]")
APP_SECRET_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/app/app_secret_key" --query "Parameter.Value" --output text 2>/dev/null || echo "")
OPENAI_API_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/openai/api_key" --query "Parameter.Value" --output text 2>/dev/null || echo "")
LANGCHAIN_API_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/langchain/api_key" --query "Parameter.Value" --output text 2>/dev/null || echo "")
E2B_API_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/e2b/api_key" --query "Parameter.Value" --output text 2>/dev/null || echo "")
SERPAPI_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/serpapi/api_key" --query "Parameter.Value" --output text 2>/dev/null || echo "")
AWS_ACCESS_KEY_ID=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/aws/access_key_id" --query "Parameter.Value" --output text 2>/dev/null || echo "")
AWS_SECRET_ACCESS_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/aws/secret_access_key" --query "Parameter.Value" --output text 2>/dev/null || echo "")
LIVEKIT_URL=$(aws --region ${AWS_REGION} ssm get-parameter --name "/${PROJECT}/${ENVIRONMENT}/livekit/url" --query "Parameter.Value" --output text 2>/dev/null || echo "ws://$${HOST_PUBLIC_DNS:-localhost}:7880")
LIVEKIT_API_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/livekit/api_key" --query "Parameter.Value" --output text 2>/dev/null || echo "devkey")
LIVEKIT_API_SECRET=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/livekit/api_secret" --query "Parameter.Value" --output text 2>/dev/null || echo "devsecret")
REMINDER_FCM_CREDENTIALS_JSON=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/reminders/fcm_credentials_json" --query "Parameter.Value" --output text 2>/dev/null || echo "")
REMINDER_FCM_PROJECT_ID=$(aws --region ${AWS_REGION} ssm get-parameter --name "/${PROJECT}/${ENVIRONMENT}/reminders/fcm_project_id" --query "Parameter.Value" --output text 2>/dev/null || echo "")
SMTP_PASSWORD=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/smtp/password" --query "Parameter.Value" --output text 2>/dev/null || echo "yrR-1ryed123")
REACT_APP_API_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/react_app/api_key" --query "Parameter.Value" --output text 2>/dev/null || echo "")

# Create keys directory for FCM credentials
mkdir -p /opt/zivohealth/keys

# Write FCM credentials to file if available from SSM
if [ -n "${REMINDER_FCM_CREDENTIALS_JSON}" ] && [ "${REMINDER_FCM_CREDENTIALS_JSON}" != "" ]; then
    echo "${REMINDER_FCM_CREDENTIALS_JSON}" > /opt/zivohealth/keys/fcm-credentials.json
    chmod 600 /opt/zivohealth/keys/fcm-credentials.json
    FCM_CREDENTIALS_PATH="/opt/zivohealth/keys/fcm-credentials.json"
    echo "✅ FCM credentials written to /opt/zivohealth/keys/fcm-credentials.json"
else
    # Don't create an empty file - this causes Firebase initialization to fail
    echo "⚠️  WARNING: No FCM credentials found in SSM parameter /${PROJECT}/${ENVIRONMENT}/reminders/fcm_credentials_json"
    echo "⚠️  FCM push notifications will be disabled until credentials are configured"
    # Remove any existing empty file
    rm -f /opt/zivohealth/keys/fcm-credentials.json
    FCM_CREDENTIALS_PATH=""
fi

# Create comprehensive .env file from production config
cat > /opt/zivohealth/.env <<ENV
# =============================================================================
# PROJECT INFORMATION
# =============================================================================
PROJECT_NAME=ZivoHealth
VERSION=0.1.0
PROJECT_VERSION=0.1.0
API_V1_STR=/api/v1
ENVIRONMENT=${ENVIRONMENT}

# =============================================================================
# SERVER SETTINGS
# =============================================================================
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# =============================================================================
# SECURITY
# =============================================================================
SECRET_KEY=$${SECRET_KEY}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# =============================================================================
# DATABASE (PostgreSQL) - from SSM Parameter Store
# =============================================================================
POSTGRES_SERVER=$${POSTGRES_SERVER}
POSTGRES_PORT=5432
POSTGRES_USER=$${POSTGRES_USER}
POSTGRES_PASSWORD=$${POSTGRES_PASSWORD}
POSTGRES_DB=zivohealth_dev

# =============================================================================
# REDIS
# =============================================================================
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_URL=redis://redis:6379/0

# =============================================================================
# OPENAI
# =============================================================================
OPENAI_API_KEY="$${OPENAI_API_KEY}"

# =============================================================================
# AWS CONFIGURATION - from EC2 IAM role (no hardcoded credentials)
# =============================================================================
AWS_ACCESS_KEY_ID=$${AWS_ACCESS_KEY_ID}
AWS_SECRET_ACCESS_KEY=$${AWS_SECRET_ACCESS_KEY}
AWS_DEFAULT_REGION=${AWS_REGION}
AWS_REGION=${AWS_REGION}
AWS_S3_BUCKET=zivohealth-data
USE_S3_UPLOADS=true
UPLOADS_S3_PREFIX=uploads/chat

# =============================================================================
# OCR CONFIGURATION
# =============================================================================
OCR_PROVIDER=aws_textract
OCR_TIMEOUT=120
OCR_MAX_FILE_SIZE=10485760

# =============================================================================
# CORS
# =============================================================================
CORS_ORIGINS=["https://app.zivohealth.ai","https://www.zivohealth.ai","https://zivohealth.ai"]

# =============================================================================
# WEBSOCKET
# =============================================================================
WS_MESSAGE_QUEUE=chat_messages
CHAT_WS_HEARTBEAT_MAX_SECONDS=300

# =============================================================================
# AI MODEL CONFIGURATION
# =============================================================================
BASE_AGENT_MODEL=o4-mini
BASE_AGENT_TEMPERATURE=1

LAB_AGENT=o4-mini
LAB_AGENT_TEMPERATURE=1
LAB_AGGREGATION_AGENT_MODEL=o4-mini
LAB_AGGREGATION_AGENT_TEMPERATURE=0.1

CUSTOMER_AGENT_MODEL=gpt-4o-mini
CUSTOMER_AGENT_TEMPERATURE=0.3

MEDICAL_DOCTOR_MODEL=gpt-4o-mini
MEDICAL_DOCTOR_TEMPERATURE=0.1

DOCUMENT_WORKFLOW_MODEL=gpt-4o-mini
DOCUMENT_WORKFLOW_TEMPERATURE=0.1

OPENAI_CLIENT_MODEL=gpt-4o-mini
DEFAULT_AI_MODEL=gpt-4o-mini

NUTRITION_VISION_MODEL=gpt-4.1-mini
NUTRITION_AGENT_MODEL=o4-mini

VITALS_VISION_MODEL=gpt-4.1-mini
VITALS_AGENT_MODEL=o4-mini

PRESCRIPTION_CLINICAL_AGENT_MODEL=o4-mini
PRESCRIPTION_CLINICAL_VISION_MODEL=gpt-4.1-mini
PRESCRIPTION_CLINICAL_VISION_MAX_TOKENS=4000

PHARMACY_AGENT_MODEL=o4-mini
PHARMACY_VISION_MODEL=gpt-4.1-mini

# =============================================================================
# AGGREGATION CONFIGURATION
# =============================================================================
VITALS_AGGREGATION_DELAY_BULK=60
VITALS_AGGREGATION_DELAY_INCREMENTAL=15
VITALS_BATCH_SIZE=20000
PROCESS_PENDING_ON_STARTUP=False

# =============================================================================
# LANGSMITH (LANGCHAIN TRACING)
# =============================================================================
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_PROJECT=zivohealth-document-workflow
LANGCHAIN_API_KEY="$${LANGCHAIN_API_KEY}"

# =============================================================================
# EXTERNAL APIs
# =============================================================================
E2B_API_KEY="$${E2B_API_KEY}"
SERPAPI_KEY="$${SERPAPI_KEY}"

# =============================================================================
# LIVEKIT (VOICE)
# =============================================================================
LIVEKIT_URL=$${LIVEKIT_URL}
LIVEKIT_API_KEY=$${LIVEKIT_API_KEY}
LIVEKIT_API_SECRET=$${LIVEKIT_API_SECRET}
LIVEKIT_KEYS=$${LIVEKIT_API_KEY}:$${LIVEKIT_API_SECRET}

# =============================================================================
# API SECURITY
# =============================================================================
VALID_API_KEYS="$${VALID_API_KEYS}"
APP_SECRET_KEY="$${APP_SECRET_KEY}"
REACT_APP_SECRET_KEY="$${APP_SECRET_KEY}"
REQUIRE_API_KEY=true
REQUIRE_APP_SIGNATURE=true

# =============================================================================
# EMAIL CONFIGURATION (PASSWORD RESET)
# =============================================================================
SMTP_SERVER=smtp.zoho.in
SMTP_PORT=587
SMTP_USERNAME=noreply@zivohealth.ai
SMTP_PASSWORD=$${SMTP_PASSWORD}
FROM_EMAIL=noreply@zivohealth.ai
FRONTEND_URL=https://api.zivohealth.ai
PASSWORD_RESET_TOKEN_EXPIRY_MINUTES=30
PASSWORD_RESET_APP_DIR=www/reset-password

# =============================================================================
# GOOGLE OAUTH
# =============================================================================
GOOGLE_CLIENT_ID=144471943832-qsmsessvagsqqmcap27oeh718beavb0h.apps.googleusercontent.com

# =============================================================================
# REMINDER SERVICE
# =============================================================================
REMINDER_SERVICE_HOST=${reminder_service_host}
REMINDER_SERVICE_PORT=${reminder_service_port}
REMINDER_RABBITMQ_URL=${reminder_rabbitmq_url}
REMINDER_RABBITMQ_EXCHANGE=${reminder_rabbitmq_exchange}
REMINDER_RABBITMQ_INPUT_QUEUE=${reminder_rabbitmq_input_queue}
REMINDER_RABBITMQ_OUTPUT_QUEUE=${reminder_rabbitmq_output_queue}
REMINDER_RABBITMQ_INPUT_ROUTING_KEY=${reminder_rabbitmq_input_routing_key}
REMINDER_RABBITMQ_OUTPUT_ROUTING_KEY=${reminder_rabbitmq_output_routing_key}
REMINDER_SCHEDULER_SCAN_INTERVAL_SECONDS=${reminder_scheduler_scan_interval_seconds}
REMINDER_SCHEDULER_BATCH_SIZE=${reminder_scheduler_batch_size}
REMINDER_METRICS_ENABLED=${reminder_metrics_enabled}
REMINDER_WORKER_CONCURRENCY=4
REMINDER_FCM_CREDENTIALS_JSON=$${FCM_CREDENTIALS_PATH}
REMINDER_FCM_PROJECT_ID=$${REMINDER_FCM_PROJECT_ID}
GOOGLE_APPLICATION_CREDENTIALS=$${FCM_CREDENTIALS_PATH}

# =============================================================================
# REACT APP (FRONTEND)
# =============================================================================
REACT_APP_API_BASE_URL=https://api.zivohealth.ai
REACT_APP_API_KEY="$${REACT_APP_API_KEY}"

ENV

## Fetch docker-compose.yml from S3 and validate
echo "Fetching rendered docker-compose.yml from S3..."
COMPOSE_TMP="/opt/zivohealth/docker-compose.yml.tmp"
COMPOSE_FINAL="/opt/zivohealth/docker-compose.yml"
LOCK_FILE="/opt/zivohealth/.compose.lock"

aws --region ${AWS_REGION} s3 cp "s3://${COMPOSE_S3_BUCKET}/${COMPOSE_S3_KEY}" "$COMPOSE_TMP"
if [ $? -ne 0 ]; then
  echo "ERROR: Failed to download docker-compose.yml from S3"
  exit 1
fi

DOWNLOADED_SHA256=$(sha256sum "$COMPOSE_TMP" | awk '{print $1}')
if [ "$DOWNLOADED_SHA256" != "${COMPOSE_SHA256}" ]; then
  echo "ERROR: Checksum mismatch for docker-compose.yml (expected ${COMPOSE_SHA256}, got $DOWNLOADED_SHA256)"
  exit 1
fi

echo "Validating docker-compose.yml syntax..."
if ! docker compose -f "$COMPOSE_TMP" config > /dev/null 2>&1; then
  echo "ERROR: Invalid docker-compose.yml syntax!"
  echo "YAML content:"
  cat "$COMPOSE_TMP"
  exit 1
fi

echo "Applying docker-compose.yml atomically..."
mkdir -p /opt/zivohealth
(
  flock 9
  mv "$COMPOSE_TMP" "$COMPOSE_FINAL"
) 9>"$LOCK_FILE"

# Start services
docker compose up -d

# Start Fail2Ban services after docker is up
echo "Starting Fail2Ban protection services..."
systemctl start fail2ban
systemctl start docker-api-logs.service

echo "ZivoHealth deployment completed successfully!"
echo "Fail2Ban API protection is active!"
