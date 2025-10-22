# Two-Tier Docker Build Strategy

This document explains the two-tier Docker image approach for faster development and deployment cycles.

## Overview

We use a **base image** containing heavy ML dependencies (torch, transformers, sentence-transformers) and an **application image** with lightweight code and dependencies. This dramatically reduces build times for day-to-day development.

## Architecture

```
┌─────────────────────────────────────┐
│   Base Image (zivohealth-base)     │
│   - python:3.11-slim                │
│   - torch (~800MB)                  │
│   - transformers (~500MB)           │
│   - sentence-transformers (~200MB)  │
│   - numpy, pandas, pillow           │
│   BUILD TIME: 10-15 minutes         │
│   FREQUENCY: Monthly/Quarterly      │
└─────────────────────────────────────┘
                  ▲
                  │ FROM
                  │
┌─────────────────────────────────────┐
│  App Image (backend/caddy/dash)     │
│  - Application code                 │
│  - Lightweight dependencies         │
│  - FastAPI, SQLAlchemy, etc.        │
│  BUILD TIME: 2-3 minutes            │
│  FREQUENCY: Daily/Multiple times    │
└─────────────────────────────────────┘
```

## Files Structure

```
backend/
├── Dockerfile                      # App image (uses base image)
├── Dockerfile.base                 # Base image (ML dependencies)
├── requirements.txt                # Original (kept for reference)
├── requirements-base.txt           # Heavy ML dependencies
└── requirements-app.txt            # Lightweight app dependencies

scripts/dev/
├── build-ml-base-image.sh            # Build & push base (RARE)
├── build-production-images.sh     # Build app images (FREQUENT)
└── push-and-deploy.sh             # Push & deploy to EC2
```

## Workflow

### Initial Setup (One-Time or Rare)

**1. Build and Push Base Image** (10-15 minutes)

Only run this when ML dependencies change in `requirements-base.txt`:

```bash
cd /path/to/ZivohealthPlatform
./scripts/dev/build-ml-base-image.sh
```

This will:
- Build the base image with torch, transformers, sentence-transformers
- Push to ECR as `zivohealth-base:latest`
- Tag it for use by application builds

### Daily Development Workflow (Fast)

**2. Build Application Images** (2-3 minutes)

Run this for code changes:

```bash
./scripts/dev/build-production-images.sh
```

This will:
- Pull the base image from ECR
- Build only the application layer
- Build backend, caddy, and dashboard images
- Complete in ~2-3 minutes (vs 10-15 minutes before)

**3. Push and Deploy to EC2**

```bash
./scripts/dev/push-and-deploy.sh
```

This will:
- Push all images to ECR
- Trigger EC2 to pull and restart services
- Deploy in ~2-3 minutes

## Build Time Comparison

| Approach | Base Build | App Build | Total Time | Frequency |
|----------|-----------|-----------|------------|-----------|
| **Old (Single-Tier)** | N/A | 10-15 min | 10-15 min | Every deploy |
| **New (Two-Tier)** | 10-15 min | 2-3 min | 2-3 min | Base: Monthly<br>App: Daily |

**Time Savings**: ~80% reduction in build time for day-to-day development!

## When to Rebuild Base Image

Rebuild the base image (`./scripts/dev/build-ml-base-image.sh`) when:

1. **Upgrading PyTorch version** (e.g., 2.0.0 → 2.1.0)
2. **Upgrading transformers version** (e.g., 4.35.0 → 4.36.0)
3. **Adding new ML libraries** to requirements-base.txt
4. **Python version upgrade** (e.g., 3.11 → 3.12)
5. **System dependencies change** in Dockerfile.base

**Typical frequency**: Every 1-3 months

## Troubleshooting

### Error: "Failed to pull base image from ECR"

**Solution**: Build the base image first:
```bash
./scripts/dev/build-ml-base-image.sh
```

### Error: "Module not found" for ML libraries

**Cause**: ML library not in base image
**Solution**: 
1. Add to `requirements-base.txt`
2. Rebuild base image: `./scripts/dev/build-ml-base-image.sh`
3. Rebuild app image: `./scripts/dev/build-production-images.sh`

### Error: "Module not found" for app libraries

**Cause**: App dependency not in requirements-app.txt
**Solution**:
1. Add to `requirements-app.txt`
2. Rebuild app image: `./scripts/dev/build-production-images.sh`

### Build is still slow

**Check**:
- Are you pulling the base image from ECR? (Should see "Pulling base image...")
- Is Docker BuildKit cache enabled?
- Is the base image properly tagged?

## Advanced Usage

### Using Different Base Image Tags

Build with a specific base image version:

```bash
# Build base with version tag
./scripts/dev/build-ml-base-image.sh v1.0.0

# Build app using specific base version
BASE_IMAGE_TAG=v1.0.0 ./scripts/dev/build-production-images.sh
```

### Local Development with Base Image

For local development, you can build both locally:

```bash
# Build base locally (one-time)
docker build -f backend/Dockerfile.base -t zivohealth-base:latest backend/

# Build app using local base
docker build \
  --build-arg BASE_IMAGE_REGISTRY=zivohealth-base \
  --build-arg BASE_IMAGE_TAG=latest \
  -t zivohealth-backend:dev \
  backend/
```

## Requirements Management

### requirements-base.txt
Heavy dependencies that rarely change:
- torch
- transformers
- sentence-transformers
- numpy
- pandas
- scipy
- pillow

### requirements-app.txt
Lightweight dependencies that change frequently:
- fastapi
- sqlalchemy
- pydantic
- uvicorn
- boto3
- langchain
- celery
- redis
- All other application dependencies

### requirements.txt
Keep the original for reference, but it's not used in builds anymore.

## CI/CD Integration

For automated deployments:

```yaml
# GitHub Actions example
jobs:
  build-base:
    # Only run when requirements-base.txt changes
    if: github.event.commits[0].modified contains 'requirements-base.txt'
    steps:
      - run: ./scripts/dev/build-ml-base-image.sh

  build-app:
    steps:
      - run: ./scripts/dev/build-production-images.sh
      - run: ./scripts/dev/push-and-deploy.sh
```

## Best Practices

1. **Version your base images**: Use semantic versioning for base images
2. **Document base changes**: Keep a changelog for base image updates
3. **Test base images**: Verify ML functionality after base image updates
4. **Cache aggressively**: Docker BuildKit caching is your friend
5. **Monitor image sizes**: Keep base image under 3GB, app under 1GB

## Questions?

Contact the DevOps team or refer to:
- [Production Deployment Guide](../scripts/dev/README.md)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)

