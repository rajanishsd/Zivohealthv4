services:
  # Main backend API
  api:
    image: ${ECR_REGISTRY_HOST}/zivohealth-production-backend:${IMAGE_TAG}
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

  # LiveKit self-hosted media server - DISABLED
  # livekit:
  #   image: livekit/livekit-server:latest
  #   container_name: zivohealth-livekit
  #   ports:
  #     - "7880:7880"
  #     - "7881:7881"
  #     - "50000-60000:50000-60000/udp"
  #   env_file:
  #     - .env
  #   environment:
  #     - LIVEKIT_KEYS=$${LIVEKIT_API_KEY}:$${LIVEKIT_API_SECRET}
  #   command: [
  #     "--bind", "0.0.0.0",
  #     "--port", "7880",
  #     "--rtc.port-range-start", "50000",
  #     "--rtc.port-range-end", "60000"
  #   ]
  #   restart: unless-stopped

  # Reminder service API
  reminders:
    image: ${ECR_REGISTRY_HOST}/zivohealth-production-backend:${IMAGE_TAG}
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
    image: ${ECR_REGISTRY_HOST}/zivohealth-production-backend:${IMAGE_TAG}
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
    image: ${ECR_REGISTRY_HOST}/zivohealth-production-backend:${IMAGE_TAG}
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

  # React Dashboard (kept separate; can be merged into caddy image later)
  dashboard:
    image: ${ECR_REGISTRY_HOST}/zivohealth-production-dashboard:${IMAGE_TAG}
    container_name: zivohealth-dashboard
    ports:
      - "3000:3000"
    environment:
      - AWS_DEFAULT_REGION=${AWS_REGION}
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
    image: ${ECR_REGISTRY_HOST}/zivohealth-production-caddy:${IMAGE_TAG}
    container_name: zivohealth-caddy
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - api
      - dashboard
    restart: unless-stopped
    environment:
      - REMINDER_SERVICE_PORT=${reminder_service_port}
    volumes:
      - caddy_data:/data
      - caddy_config:/config

volumes:
  caddy_data:
  caddy_config:

