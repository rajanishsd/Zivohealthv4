# Multi-stage build for a small runtime image
FROM python:3.11-slim AS python-builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /w
RUN apt-get update -y && apt-get install -y --no-install-recommends build-essential gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /w/requirements.txt
RUN pip wheel --no-cache-dir --wheel-dir /w/wheels -r /w/requirements.txt

# React app builder stage
FROM node:18-alpine AS react-builder
WORKDIR /app
COPY password-reset-app/package*.json ./
RUN npm install --omit=dev
COPY password-reset-app/ ./
RUN npm run build

# Final runtime stage
FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY --from=python-builder /w/wheels /wheels
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r /app/requirements.txt && rm -rf /wheels

# Copy backend code
COPY app/ /app/app/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/
COPY run.py /app/

# Copy built React app from react-builder stage
COPY --from=react-builder /app/build/ /app/www/reset-password/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
