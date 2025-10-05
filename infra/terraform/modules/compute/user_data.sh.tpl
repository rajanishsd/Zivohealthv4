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

# Create basic application directory
mkdir -p /opt/zivohealth
cd /opt/zivohealth

# Get database configuration from SSM parameters
POSTGRES_SERVER=$(aws --region ${AWS_REGION} ssm get-parameter --name "/${PROJECT}/${ENVIRONMENT}/db/host" --query "Parameter.Value" --output text 2>/dev/null || echo "localhost")
POSTGRES_USER=$(aws --region ${AWS_REGION} ssm get-parameter --name "/${PROJECT}/${ENVIRONMENT}/db/user" --query "Parameter.Value" --output text 2>/dev/null || echo "zivo")
POSTGRES_PASSWORD=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/db/password" --query "Parameter.Value" --output text 2>/dev/null || echo "changeme")

# Get other configuration from SSM parameters
SECRET_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/app/secret_key" --query "Parameter.Value" --output text 2>/dev/null || echo "zivohealth900")
# VALID_API_KEYS is stored under /api/valid_api_keys
VALID_API_KEYS=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/api/valid_api_keys" --query "Parameter.Value" --output text 2>/dev/null || echo "[]")
# App-level HMAC secret for request signatures
APP_SECRET_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/app/app_secret_key" --query "Parameter.Value" --output text 2>/dev/null || echo "")
OPENAI_API_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/openai/api_key" --query "Parameter.Value" --output text 2>/dev/null || echo "")
# LangChain and other external API keys
LANGCHAIN_API_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/langchain/api_key" --query "Parameter.Value" --output text 2>/dev/null || echo "")
E2B_API_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/e2b/api_key" --query "Parameter.Value" --output text 2>/dev/null || echo "")
SERPAPI_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/serpapi/api_key" --query "Parameter.Value" --output text 2>/dev/null || echo "")
AWS_ACCESS_KEY_ID=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/aws/access_key_id" --query "Parameter.Value" --output text 2>/dev/null || echo "")
AWS_SECRET_ACCESS_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/aws/secret_access_key" --query "Parameter.Value" --output text 2>/dev/null || echo "")

# LiveKit configuration from SSM (fallbacks provided)
LIVEKIT_URL=$(aws --region ${AWS_REGION} ssm get-parameter --name "/${PROJECT}/${ENVIRONMENT}/livekit/url" --query "Parameter.Value" --output text 2>/dev/null || echo "ws://$${HOST_PUBLIC_DNS:-localhost}:7880")
LIVEKIT_API_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/livekit/api_key" --query "Parameter.Value" --output text 2>/dev/null || echo "devkey")
LIVEKIT_API_SECRET=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/livekit/api_secret" --query "Parameter.Value" --output text 2>/dev/null || echo "devsecret")

# Get reminder-specific config from SSM
REMINDER_FCM_CREDENTIALS_JSON=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/reminders/fcm_credentials_json" --query "Parameter.Value" --output text 2>/dev/null || echo "")
REMINDER_FCM_PROJECT_ID=$(aws --region ${AWS_REGION} ssm get-parameter --name "/${PROJECT}/${ENVIRONMENT}/reminders/fcm_project_id" --query "Parameter.Value" --output text 2>/dev/null || echo "")

# Get SMTP password from SSM
SMTP_PASSWORD=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/smtp/password" --query "Parameter.Value" --output text 2>/dev/null || echo "changeme")

# Get REACT_APP_API_KEY from SSM
REACT_APP_API_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/react_app/api_key" --query "Parameter.Value" --output text 2>/dev/null || echo "")

# Create keys directory for FCM credentials
mkdir -p /opt/zivohealth/keys

# Write FCM credentials to file if available from SSM
if [ -n "$${REMINDER_FCM_CREDENTIALS_JSON}" ] && [ "$${REMINDER_FCM_CREDENTIALS_JSON}" != "" ]; then
    echo "$${REMINDER_FCM_CREDENTIALS_JSON}" > /opt/zivohealth/keys/fcm-credentials.json
    chmod 600 /opt/zivohealth/keys/fcm-credentials.json
    FCM_CREDENTIALS_PATH="/opt/zivohealth/keys/fcm-credentials.json"
    echo "✅ FCM credentials written to /opt/zivohealth/keys/fcm-credentials.json"
else
    # Don't create an empty file - this causes Firebase initialization to fail
    echo "⚠️  WARNING: No FCM credentials found in SSM parameter /$${PROJECT}/$${ENVIRONMENT}/reminders/fcm_credentials_json"
    echo "⚠️  FCM push notifications will be disabled until credentials are configured"
    # Remove any existing empty file
    rm -f /opt/zivohealth/keys/fcm-credentials.json
    FCM_CREDENTIALS_PATH=""
fi

# Note: The keys from backend/keys/ are copied into the Docker image during build
# and will be available at /app/keys/ inside the container

# Create comprehensive .env file with all required variables
cat > /opt/zivohealth/.env <<ENV
# Project Information
PROJECT_NAME=ZivoHealth
VERSION=0.1.0
PROJECT_VERSION=0.1.0
API_V1_STR=/api/v1
ENVIRONMENT=${ENVIRONMENT}

# Server settings
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# Security
SECRET_KEY=$${SECRET_KEY}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Database
POSTGRES_SERVER=$${POSTGRES_SERVER}
POSTGRES_PORT=5432
POSTGRES_USER=$${POSTGRES_USER}
POSTGRES_PASSWORD=$${POSTGRES_PASSWORD}
POSTGRES_DB=zivohealth_dev

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_URL=redis://redis:6379/0

# OpenAI
# Quote to avoid any accidental truncation or parsing issues (e.g., keys starting with sk-)
OPENAI_API_KEY="$${OPENAI_API_KEY}"

# AWS Configuration
AWS_ACCESS_KEY_ID=$${AWS_ACCESS_KEY_ID}
AWS_SECRET_ACCESS_KEY=$${AWS_SECRET_ACCESS_KEY}
AWS_DEFAULT_REGION=$${AWS_REGION}
AWS_REGION=$${AWS_REGION}
AWS_S3_BUCKET=zivohealth-data

# OCR Configuration
OCR_PROVIDER=aws_textract
OCR_TIMEOUT=120
OCR_MAX_FILE_SIZE=10485760

# CORS
CORS_ORIGINS=["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000", "http://127.0.0.1:8000"]

# WebSocket
WS_MESSAGE_QUEUE=chat_messages

# AI MODEL CONFIGURATION
BASE_AGENT_MODEL=o4-mini
BASE_AGENT_TEMPERATURE=1
LAB_AGENT=o4-mini
LAB_AGENT_TEMPERATURE=1
CUSTOMER_AGENT_MODEL=gpt-4o-mini
CUSTOMER_AGENT_TEMPERATURE=0.3
MEDICAL_DOCTOR_MODEL=gpt-4o-mini
MEDICAL_DOCTOR_TEMPERATURE=0.1
DOCUMENT_WORKFLOW_MODEL=gpt-4o-mini
DOCUMENT_WORKFLOW_TEMPERATURE=0.1
OPENAI_CLIENT_MODEL=gpt-4o-mini
DEFAULT_AI_MODEL=gpt-4o-mini

# Vitals Aggregation
VITALS_AGGREGATION_DELAY_BULK=60
VITALS_AGGREGATION_DELAY_INCREMENTAL=15
VITALS_BATCH_SIZE=20000
PROCESS_PENDING_ON_STARTUP=False

# LangSmith Configuration
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_PROJECT=zivohealth-document-workflow
LANGCHAIN_API_KEY="$${LANGCHAIN_API_KEY}"

# Lab Aggregation Agent
LAB_AGGREGATION_AGENT_MODEL=o4-mini
LAB_AGGREGATION_AGENT_TEMPERATURE=0.1

# Nutrition Agent
NUTRITION_VISION_MODEL=gpt-4.1-mini
NUTRITION_AGENT_MODEL=o4-mini

# External APIs
E2B_API_KEY="$${E2B_API_KEY}"
SERPAPI_KEY="$${SERPAPI_KEY}"

# Vitals Agent Models
VITALS_VISION_MODEL=gpt-4.1-mini
VITALS_AGENT_MODEL=o4-mini

# Prescription Clinical Agent Models
PRESCRIPTION_CLINICAL_AGENT_MODEL=o4-mini
PRESCRIPTION_CLINICAL_VISION_MODEL=gpt-4.1-mini
PRESCRIPTION_CLINICAL_VISION_MAX_TOKENS=4000

# Pharmacy Agent Models
PHARMACY_AGENT_MODEL=o4-mini
PHARMACY_VISION_MODEL=gpt-4.1-mini

# LiveKit Configuration
LIVEKIT_URL=$${LIVEKIT_URL}
LIVEKIT_API_KEY=$${LIVEKIT_API_KEY}
LIVEKIT_API_SECRET=$${LIVEKIT_API_SECRET}
# Convenience combined key for LiveKit server container
LIVEKIT_KEYS=$${LIVEKIT_API_KEY}:$${LIVEKIT_API_SECRET}

# S3 Configuration
UPLOADS_S3_PREFIX=uploads/chat

# API Security
VALID_API_KEYS="$${VALID_API_KEYS}"
APP_SECRET_KEY="$${APP_SECRET_KEY}"
REQUIRE_API_KEY=true
REQUIRE_APP_SIGNATURE=true

# Dashboard Configuration
REACT_APP_API_BASE_URL=https://api.zivohealth.ai
REACT_APP_API_KEY="$${REACT_APP_API_KEY}"

# Email Configuration
SMTP_SERVER=smtp.zoho.in
SMTP_PORT=587
SMTP_USERNAME=rajanish@zivohealth.ai
SMTP_PASSWORD="$${SMTP_PASSWORD}"
FROM_EMAIL=rajanish@zivohealth.ai
FRONTEND_URL=https://zivohealth.ai
PASSWORD_RESET_TOKEN_EXPIRY_MINUTES=30

# Password Reset App Configuration
PASSWORD_RESET_APP_DIR=www/reset-password

# Reminder Service Configuration
REMINDER_SERVICE_URL=http://reminders:${reminder_service_port}
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

# WebSocket Configuration
CHAT_WS_HEARTBEAT_MAX_SECONDS=300
ENV

# Create docker-compose.yml with reminder service
cat > /opt/zivohealth/docker-compose.yml <<COMPOSE
services:
  # Main backend API
  api:
    image: $${ECR_REPO_URL:-474221740916.dkr.ecr.us-east-1.amazonaws.com/zivohealth-dev-backend}:$${IMAGE_TAG:-latest}
    container_name: zivohealth-api
    ports:
      - "8000:8000"
    environment:
      - AWS_DEFAULT_REGION=${AWS_REGION}
    env_file:
      - .env
    volumes:
      - ./keys:/app/keys:ro
    depends_on:
      - redis
      - rabbitmq
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # LiveKit self-hosted media server
  livekit:
    image: livekit/livekit-server:latest
    container_name: zivohealth-livekit
    ports:
      - "7880:7880"   # HTTP/WS signaling
      - "7881:7881"   # TCP fallback/TURN
      - "50000-60000:50000-60000/udp"  # RTP/RTCP media
    env_file:
      - .env
    environment:
      # Many LiveKit deployments use LIVEKIT_KEYS env var in the format key:secret
      - LIVEKIT_KEYS=$${LIVEKIT_KEYS}
    command: [
      "--bind", "0.0.0.0",
      "--port", "7880",
      "--rtc.port-range-start", "50000",
      "--rtc.port-range-end", "60000"
    ]
    restart: unless-stopped

  # Reminder service API
  reminders:
    image: $${ECR_REPO_URL:-474221740916.dkr.ecr.us-east-1.amazonaws.com/zivohealth-dev-backend}:$${IMAGE_TAG:-latest}
    container_name: zivohealth-reminders
    ports:
      - "${reminder_service_port}:${reminder_service_port}"
    environment:
      - AWS_DEFAULT_REGION=${AWS_REGION}
    env_file:
      - .env
    volumes:
      - ./keys:/app/keys:ro
    command: ["python", "-m", "uvicorn", "app.reminders.service:app", "--host", "0.0.0.0", "--port", "${reminder_service_port}"]
    depends_on:
      - redis
      - rabbitmq
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:${reminder_service_port}/api/v1/reminders/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Reminder Celery worker
  reminders-worker:
    image: $${ECR_REPO_URL:-474221740916.dkr.ecr.us-east-1.amazonaws.com/zivohealth-dev-backend}:$${IMAGE_TAG:-latest}
    container_name: zivohealth-reminders-worker
    environment:
      - AWS_DEFAULT_REGION=${AWS_REGION}
    env_file:
      - .env
    volumes:
      - ./keys:/app/keys:ro
    command: ["python", "-m", "celery", "-A", "app.reminders.celery_app:celery_app", "worker", "--loglevel=INFO", "-Q", "reminders.input.v1,reminders.output.v1", "--concurrency=4"]
    depends_on:
      - redis
      - rabbitmq
    restart: unless-stopped

  # Reminder Celery beat scheduler
  reminders-beat:
    image: $${ECR_REPO_URL:-474221740916.dkr.ecr.us-east-1.amazonaws.com/zivohealth-dev-backend}:$${IMAGE_TAG:-latest}
    container_name: zivohealth-reminders-beat
    environment:
      - AWS_DEFAULT_REGION=${AWS_REGION}
    env_file:
      - .env
    volumes:
      - ./keys:/app/keys:ro
    command: ["python", "-m", "celery", "-A", "app.reminders.celery_app:celery_app", "beat", "--loglevel=INFO"]
    depends_on:
      - redis
      - rabbitmq
    restart: unless-stopped

  # Note: PostgreSQL is managed by RDS, not docker-compose

  # Redis for caching and Celery
  redis:
    image: redis:7-alpine
    container_name: zivohealth-redis
    ports:
      - "6379:6379"
    restart: unless-stopped

            # RabbitMQ for Celery message broker
            rabbitmq:
                image: rabbitmq:3-management
                container_name: zivohealth-rabbitmq
                environment:
                  RABBITMQ_DEFAULT_USER: guest
                  RABBITMQ_DEFAULT_PASS: guest
                ports:
                  - "5672:5672"
                  - "15672:15672"
                restart: unless-stopped

            # React Dashboard (production: serve built files)
            dashboard:
                image: $${ECR_REPO_URL:-474221740916.dkr.ecr.us-east-1.amazonaws.com/zivohealth-dev-backend}:$${IMAGE_TAG:-latest}
                container_name: zivohealth-dashboard
                ports:
                  - "3000:3000"
                environment:
                  - AWS_DEFAULT_REGION=us-east-1
                env_file:
                  - .env
                depends_on:
                  - api
                restart: unless-stopped
                healthcheck:
                  test: ["CMD", "curl", "-f", "http://localhost:3000"]
                  interval: 30s
                  timeout: 10s
                  retries: 3



  # Caddy reverse proxy
  caddy:
    image: public.ecr.aws/docker/library/caddy:2-alpine
    container_name: zivohealth-caddy
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
                depends_on:
                  - api
                  - livekit
                  - dashboard
    environment:
      - REMINDER_SERVICE_PORT=${reminder_service_port}

volumes:
  caddy_data:
  caddy_config:

# No volumes needed since PostgreSQL is managed by RDS
COMPOSE

# Create Caddyfile for reverse proxy
cat > /opt/zivohealth/Caddyfile <<CADDY
api.zivohealth.ai {
    encode zstd gzip

    @reminders path /api/v1/reminders*
    handle @reminders {
        reverse_proxy reminders:{$REMINDER_SERVICE_PORT}
    }

    reverse_proxy api:8000
}

zivohealth.ai, www.zivohealth.ai {
    encode zstd gzip

    # Route dashboard requests to dashboard service
    handle /dashboard* {
        reverse_proxy dashboard:3000
    }

    # Route password reset requests to backend API
    handle /reset-password* {
        reverse_proxy api:8000
    }

    # Route Reminders API to reminders service
    handle /api/v1/reminders* {
        reverse_proxy reminders:{$REMINDER_SERVICE_PORT}
    }

    # Route other API requests to backend
    handle /api/* {
        reverse_proxy api:8000
    }

    # Route health checks to backend
    handle /health {
        reverse_proxy api:8000
    }

    # Serve all other requests as static files
    root * /srv/www
    file_server
}
CADDY

echo "Docker Compose configuration created with reminder service and Caddy reverse proxy!"