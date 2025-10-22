# Lightweight API Image - No ML dependencies
# The API only makes OpenAI API calls and doesn't need local ML models
# ML workloads are handled by the separate Fargate ML Worker service

# React app builder stage
FROM node:18-alpine AS react-builder
WORKDIR /app
COPY password-reset-app/package*.json ./
RUN npm install --omit=dev
COPY password-reset-app/ ./
RUN npm run build

# Python dependencies builder stage
FROM python:3.11-slim AS python-builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /w
RUN apt-get update -y && apt-get install -y --no-install-recommends build-essential gcc && rm -rf /var/lib/apt/lists/*
COPY requirements-app.txt /w/requirements-app.txt
RUN pip wheel --no-cache-dir --wheel-dir /w/wheels -r /w/requirements-app.txt

# Final runtime stage - Lightweight Python base
FROM python:3.11-slim

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install application dependencies (lightweight packages only)
COPY --from=python-builder /w/wheels /wheels
COPY requirements-app.txt /app/requirements-app.txt
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r /app/requirements-app.txt && rm -rf /wheels

# Copy backend code
COPY app/ /app/app/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/
COPY run.py /app/

# Copy keys folder for FCM credentials
COPY keys/ /app/keys/

# Copy diagnostic and utility scripts
COPY scripts/ /app/scripts/

# Copy LOINC mapper for lab categorization
COPY 3PData/loinc/ /app/3PData/loinc/

# Copy built React app from react-builder stage
COPY --from=react-builder /app/build/ /app/www/reset-password/

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
