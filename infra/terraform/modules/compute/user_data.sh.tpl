#!/bin/bash
set -e

export AWS_DEFAULT_REGION=${AWS_REGION}

# Install updates, awscli, and SSM Agent
apt-get update -y || true
apt-get install -y ca-certificates curl gnupg lsb-release awscli || true

# Ensure SSM Agent is installed and running (Ubuntu 22.04 ships with it, but keep idempotent)
if ! systemctl status snap.amazon-ssm-agent.amazon-ssm-agent >/dev/null 2>&1; then
  snap install amazon-ssm-agent || true
  systemctl enable --now snap.amazon-ssm-agent.amazon-ssm-agent || true
fi

if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
    tee /etc/apt/sources.list.d/docker.list > /dev/null
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

usermod -aG docker ubuntu || true

mkdir -p /opt/zivohealth
cd /opt/zivohealth

# Write docker-compose.yml
cat > /opt/zivohealth/docker-compose.yml <<'YAML'
services:
  api:
    image: ${ECR_REPO_URL}:${IMAGE_TAG}
    env_file:
      - .env
    expose:
      - "8000"
    restart: always
    depends_on:
      - redis
  caddy:
    image: public.ecr.aws/docker/library/caddy:2-alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./www:/srv/www:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - api
  redis:
    image: public.ecr.aws/docker/library/redis:7-alpine
    restart: always
volumes:
  caddy_data:
  caddy_config:
YAML

# Populate .env from SSM
PROJECT=${PROJECT}
ENVIRONMENT=${ENVIRONMENT}
DB_HOST=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name /${PROJECT}/${ENVIRONMENT}/db/host --query "Parameter.Value" --output text || echo "")
DB_USER=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name /${PROJECT}/${ENVIRONMENT}/db/user --query "Parameter.Value" --output text || echo "")
DB_PASS=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name /${PROJECT}/${ENVIRONMENT}/db/password --query "Parameter.Value" --output text || echo "")
S3_BUCKET=$(aws --region ${AWS_REGION} ssm get-parameter --name /${PROJECT}/${ENVIRONMENT}/s3/bucket --query "Parameter.Value" --output text || echo "")
VALID_API_KEYS_SSM=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/api/valid_api_keys" --query "Parameter.Value" --output text 2>/dev/null || echo "")

# Optional application secrets/config from SSM (if present)
OPENAI_API_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/openai/api_key" --query "Parameter.Value" --output text 2>/dev/null || echo "")
LANGCHAIN_API_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/langsmith/api_key" --query "Parameter.Value" --output text 2>/dev/null || echo "")
LANGCHAIN_PROJECT=$(aws --region ${AWS_REGION} ssm get-parameter --name "/${PROJECT}/${ENVIRONMENT}/langsmith/project" --query "Parameter.Value" --output text 2>/dev/null || echo "")
LANGCHAIN_ENDPOINT=$(aws --region ${AWS_REGION} ssm get-parameter --name "/${PROJECT}/${ENVIRONMENT}/langsmith/endpoint" --query "Parameter.Value" --output text 2>/dev/null || echo "")
E2B_API_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/e2b/api_key" --query "Parameter.Value" --output text 2>/dev/null || echo "")
SERPAPI_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/serpapi/key" --query "Parameter.Value" --output text 2>/dev/null || echo "")
LIVEKIT_URL=$(aws --region ${AWS_REGION} ssm get-parameter --name "/${PROJECT}/${ENVIRONMENT}/livekit/url" --query "Parameter.Value" --output text 2>/dev/null || echo "")
LIVEKIT_API_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/livekit/api_key" --query "Parameter.Value" --output text 2>/dev/null || echo "")
LIVEKIT_API_SECRET=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/livekit/api_secret" --query "Parameter.Value" --output text 2>/dev/null || echo "")

# Create a script to fetch all SSM parameters and update .env
cat > /opt/zivohealth/update_env_from_ssm.sh <<'SSM_SCRIPT'
#!/bin/bash
set -e

PROJECT=${PROJECT}
ENVIRONMENT=${ENVIRONMENT}
AWS_REGION=${AWS_REGION}

# Function to get SSM parameter with fallback
get_ssm_param() {
  local name="$$1"
  local default="$$2"
  local decrypt="$${3:-false}"
  
  if [ "$$decrypt" = "true" ]; then
    aws --region $$AWS_REGION ssm get-parameter --with-decryption --name "$$name" --query "Parameter.Value" --output text 2>/dev/null || echo "$$default"
  else
    aws --region $$AWS_REGION ssm get-parameter --name "$$name" --query "Parameter.Value" --output text 2>/dev/null || echo "$$default"
  fi
}

# Get all configuration from SSM
SMTP_SERVER=$$(get_ssm_param "/$$PROJECT/$$ENVIRONMENT/email/smtp_server" "")
SMTP_PORT=$$(get_ssm_param "/$$PROJECT/$$ENVIRONMENT/email/smtp_port" "")
SMTP_USERNAME=$$(get_ssm_param "/$$PROJECT/$$ENVIRONMENT/email/smtp_username" "")
SMTP_PASSWORD=$$(get_ssm_param "/$$PROJECT/$$ENVIRONMENT/email/smtp_password" "" true)
FROM_EMAIL=$$(get_ssm_param "/$$PROJECT/$$ENVIRONMENT/email/from_email" "")
FRONTEND_URL=$$(get_ssm_param "/$$PROJECT/$$ENVIRONMENT/email/frontend_url" "")
PASSWORD_RESET_BASE_URL=$$(get_ssm_param "/$$PROJECT/$$ENVIRONMENT/email/password_reset_base_url" "")
PASSWORD_RESET_TOKEN_EXPIRY_MINUTES=$$(get_ssm_param "/$$PROJECT/$$ENVIRONMENT/email/password_reset_token_expiry_minutes" "")

# Add email configuration to .env if not already present
if ! grep -q "SMTP_SERVER" /opt/zivohealth/.env; then
  echo "" >> /opt/zivohealth/.env
  echo "# Email Configuration" >> /opt/zivohealth/.env
  echo "SMTP_SERVER=$$SMTP_SERVER" >> /opt/zivohealth/.env
  echo "SMTP_PORT=$$SMTP_PORT" >> /opt/zivohealth/.env
  echo "SMTP_USERNAME=$$SMTP_USERNAME" >> /opt/zivohealth/.env
  echo "SMTP_PASSWORD=$$SMTP_PASSWORD" >> /opt/zivohealth/.env
  echo "FROM_EMAIL=$$FROM_EMAIL" >> /opt/zivohealth/.env
  echo "FRONTEND_URL=$$FRONTEND_URL" >> /opt/zivohealth/.env
  echo "PASSWORD_RESET_BASE_URL=$$PASSWORD_RESET_BASE_URL" >> /opt/zivohealth/.env
  echo "PASSWORD_RESET_TOKEN_EXPIRY_MINUTES=$$PASSWORD_RESET_TOKEN_EXPIRY_MINUTES" >> /opt/zivohealth/.env
fi
SSM_SCRIPT

chmod +x /opt/zivohealth/update_env_from_ssm.sh
/opt/zivohealth/update_env_from_ssm.sh


# Secret key: fetch from SSM if available, otherwise generate a random one for this instance
SECRET_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/app/secret_key" --query "Parameter.Value" --output text 2>/dev/null || echo "")
if [ -z "$SECRET_KEY" ]; then
  SECRET_KEY=$(head -c 32 /dev/urandom | base64 | tr -d '\n')
fi

# App secret for HMAC signatures
APP_SECRET_KEY=${APP_SECRET_KEY_OVERRIDE}
if [ -z "$APP_SECRET_KEY" ]; then
  APP_SECRET_KEY=$(aws --region ${AWS_REGION} ssm get-parameter --with-decryption --name "/${PROJECT}/${ENVIRONMENT}/app/app_secret_key" --query "Parameter.Value" --output text 2>/dev/null || echo "")
fi
if [ -z "$APP_SECRET_KEY" ]; then
  APP_SECRET_KEY=$(head -c 32 /dev/urandom | base64 | tr -d '\n')
fi

# --- API keys: use SSM if present, otherwise generate one so the system is usable ---
if [ -n "${VALID_API_KEYS_OVERRIDE}" ]; then
  VALID_API_KEYS="${VALID_API_KEYS_OVERRIDE}"
elif [ -n "$VALID_API_KEYS_SSM" ]; then
  VALID_API_KEYS="$VALID_API_KEYS_SSM"
else
  GEN_KEY=$(head -c 32 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32)
  VALID_API_KEYS="[\"$GEN_KEY\"]"
  echo "{\"api_keys\": [$GEN_KEY]}" > /opt/zivohealth/generated_api_keys.json || true
fi

# AI Model Configuration will be added by the update script

cat > /opt/zivohealth/.env <<ENV
# Project Information
PROJECT_NAME=ZivoHealth
VERSION=0.1.0
PROJECT_VERSION=0.1.0
API_V1_STR=/api/v1

# Server settings
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
PROCESS_PENDING_ON_STARTUP=false

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# Database
POSTGRES_SERVER=$${DB_HOST}
POSTGRES_PORT=5432
POSTGRES_DB=$${PROJECT}_$${ENVIRONMENT}
POSTGRES_USER=$${DB_USER}
POSTGRES_PASSWORD=$${DB_PASS}

# Security
SECRET_KEY=$${SECRET_KEY}
APP_SECRET_KEY=$${APP_SECRET_KEY}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
VALID_API_KEYS=$${VALID_API_KEYS}
REQUIRE_API_KEY=true
REQUIRE_APP_SIGNATURE=false

# AWS
AWS_DEFAULT_REGION=${AWS_REGION}
AWS_REGION=${AWS_REGION}
AWS_S3_BUCKET=$${S3_BUCKET}
USE_S3_UPLOADS=true

# File Uploads
UPLOADS_S3_PREFIX=

# OCR Configuration
OCR_PROVIDER=aws_textract
OCR_TIMEOUT=120
OCR_MAX_FILE_SIZE=10485760

# CORS
CORS_ORIGINS=["https://app.zivohealth.ai", "https://www.zivohealth.ai", "https://zivohealth.ai"]

# WebSocket
WS_MESSAGE_QUEUE=chat_messages

# Vitals Aggregation
VITALS_BATCH_SIZE=20000
VITALS_AGGREGATION_DELAY_BULK=60
VITALS_AGGREGATION_DELAY_INCREMENTAL=15

# Optional Integrations (populated from SSM if available)
OPENAI_API_KEY=$${OPENAI_API_KEY}
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=$${LANGCHAIN_ENDPOINT}
LANGCHAIN_PROJECT=$${LANGCHAIN_PROJECT}
LANGCHAIN_API_KEY=$${LANGCHAIN_API_KEY}
E2B_API_KEY=$${E2B_API_KEY}
SERPAPI_KEY=$${SERPAPI_KEY}
LIVEKIT_URL=$${LIVEKIT_URL}
LIVEKIT_API_KEY=$${LIVEKIT_API_KEY}
LIVEKIT_API_SECRET=$${LIVEKIT_API_SECRET}

# Email Configuration and AI Model Configuration will be added by the update script
ENV

# Ensure compose image variables are available from .env as well
echo "ECR_REPO_URL=${ECR_REPO_URL}" >> /opt/zivohealth/.env
echo "IMAGE_TAG=${IMAGE_TAG}" >> /opt/zivohealth/.env

# Prepare static site content for apex/www
mkdir -p /opt/zivohealth/www
cat > /opt/zivohealth/www/index.html <<'HTML'

HTML

# Write Caddyfile for automatic HTTPS, with API on api.zivohealth.ai and static apex/www
cat > /opt/zivohealth/Caddyfile <<'CADDY'
api.zivohealth.ai {
  encode zstd gzip
  reverse_proxy api:8000
}

zivohealth.ai, www.zivohealth.ai {
  encode zstd gzip
  
  # Route password reset requests to backend API
  handle /reset-password* {
    reverse_proxy api:8000
  }
  
  # Serve all other requests as static files
  root * /srv/www
  file_server
}
CADDY

# Systemd service
cat > /etc/systemd/system/zivohealth.service <<'UNIT'
[Unit]
Description=ZivoHealth Docker Compose
After=network.target docker.service
Requires=docker.service

[Service]
Type=oneshot
WorkingDirectory=/opt/zivohealth
Environment=ECR_REPO_URL=${ECR_REPO_URL}
Environment=IMAGE_TAG=${IMAGE_TAG}
ExecStartPre=/bin/bash -lc '/usr/bin/aws ecr get-login-password --region ${AWS_REGION} | /usr/bin/docker login --username AWS --password-stdin $(echo ${ECR_REPO_URL} | cut -d"/" -f1)'
ExecStartPre=/usr/bin/docker pull public.ecr.aws/docker/library/redis:7-alpine
ExecStart=/usr/bin/docker compose up -d
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now zivohealth.service

# Wait for services to start
sleep 30

# Deploy password reset app
echo "🚀 Deploying password reset app..."
mkdir -p /srv/www
docker cp zivohealth-api-1:/app/www/reset-password /srv/www/ || echo "⚠️ Password reset app not found in container"
chown -R root:root /srv/www/reset-password
chmod -R 755 /srv/www/reset-password

# Restart Caddy to pick up the new files
docker restart zivohealth-caddy-1

echo "✅ Password reset app deployment completed!"

