#!/bin/bash
set -e

# Add Caddyfile and dashboard service to existing setup
echo "Adding Caddyfile and dashboard service..."

# Create Caddyfile
cat > /opt/zivohealth/Caddyfile <<CADDY
api.zivohealth.ai {
    encode zstd gzip

    @reminders path /api/v1/reminders*
    handle @reminders {
        reverse_proxy reminders:${REMINDER_SERVICE_PORT}
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
        reverse_proxy reminders:${REMINDER_SERVICE_PORT}
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

# Add dashboard service to docker-compose.yml
echo "Adding dashboard service to docker-compose.yml..."

# Create a backup
cp /opt/zivohealth/docker-compose.yml /opt/zivohealth/docker-compose.yml.backup

# Add dashboard service to docker-compose.yml
cat >> /opt/zivohealth/docker-compose.yml <<'DASHBOARD_SERVICE'

  # React Dashboard
  dashboard:
    image: ${ECR_REPO_URL:-474221740916.dkr.ecr.us-east-1.amazonaws.com/zivohealth-dev-backend}:${IMAGE_TAG:-latest}
    container_name: zivohealth-dashboard
    ports:
      - "3000:3000"
    environment:
      - AWS_DEFAULT_REGION=${AWS_REGION}
    env_file:
      - .env
    command: ["npm", "start", "--prefix", "/app/backend-dashboard"]
    depends_on:
      - api
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000"]
      interval: 30s
      timeout: 10s
      retries: 3
DASHBOARD_SERVICE

# Update caddy dependencies to include dashboard
sed -i 's/depends_on:/depends_on:\
      - dashboard/' /opt/zivohealth/docker-compose.yml

# Restart services to apply changes
echo "Restarting services with Caddy and dashboard..."
cd /opt/zivohealth
docker compose down
docker compose up -d

echo "Caddyfile and dashboard service added successfully!"
