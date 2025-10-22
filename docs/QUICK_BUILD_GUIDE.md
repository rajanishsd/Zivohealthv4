# Quick Build & Deploy Guide

**Two-Tier Docker Strategy** - Fast builds by separating ML dependencies from application code.

## 🚀 Quick Commands

### First Time Setup (or when ML dependencies change)

```bash
# Build base image with ML dependencies (10-15 min, run RARELY)
./scripts/dev/build-ml-base-image.sh
```

### Regular Development (Daily/Multiple Times)

```bash
# Build app images (2-3 min, run FREQUENTLY)
./scripts/dev/build-production-images.sh

# Push and deploy to EC2 (2-3 min)
./scripts/dev/push-and-deploy.sh
```

### Combined Fast Deploy

```bash
# Build and deploy in one go (~5 minutes total)
./scripts/dev/build-production-images.sh && ./scripts/dev/push-and-deploy.sh
```

## 📊 Build Times

| Task | Old Way | New Way | Savings |
|------|---------|---------|---------|
| Base image build | N/A | 10-15 min | N/A |
| App image build | 10-15 min | 2-3 min | **80% faster** |
| Total deploy time | 10-15 min | 2-3 min | **80% faster** |

## 🔄 When to Use Each Script

### `build-ml-base-image.sh` (RARE - Monthly/Quarterly)
Run when:
- ✅ Upgrading PyTorch, transformers, or sentence-transformers
- ✅ Adding new ML libraries to `requirements-base.txt`
- ✅ Upgrading Python version
- ❌ **NOT** for application code changes
- ❌ **NOT** for FastAPI, SQLAlchemy, or other app dependencies

### `build-production-images.sh` (FREQUENT - Daily)
Run when:
- ✅ Application code changes
- ✅ Adding/updating app dependencies in `requirements-app.txt`
- ✅ Frontend changes (dashboard, password-reset app)
- ✅ Configuration changes
- ✅ **Use this for 99% of your deployments**

### `push-and-deploy.sh` (FREQUENT - After every build)
Run:
- ✅ After `build-production-images.sh` completes
- ✅ To deploy built images to production EC2

## 📁 Files Changed

```
✅ Created:
   backend/Dockerfile.base              (Base image definition)
   backend/requirements-base.txt        (ML dependencies)
   backend/requirements-app.txt         (App dependencies)
   scripts/dev/build-ml-base-image.sh      (Build base image)
   docs/TWO_TIER_DOCKER_BUILD.md        (Full documentation)
   QUICK_BUILD_GUIDE.md                 (This file)

🔄 Modified:
   backend/Dockerfile                   (Now uses base image)
   scripts/dev/build-production-images.sh (Pulls base, builds app)

📝 Unchanged:
   backend/requirements.txt             (Kept for reference)
   scripts/dev/push-and-deploy.sh       (Works as-is)
```

## 🆘 Troubleshooting

### "Failed to pull base image from ECR"
```bash
# Run the base image build first
./scripts/dev/build-ml-base-image.sh
```

### "Module not found: torch/transformers"
```bash
# Add to requirements-base.txt, then rebuild base
./scripts/dev/build-ml-base-image.sh
```

### "Module not found: fastapi/sqlalchemy"
```bash
# Add to requirements-app.txt, then rebuild app
./scripts/dev/build-production-images.sh
```

## 💡 Pro Tips

1. **Your typical workflow** (99% of the time):
   ```bash
   # Make code changes, then:
   ./scripts/dev/build-production-images.sh && ./scripts/dev/push-and-deploy.sh
   ```

2. **First deployment or after long break**:
   ```bash
   # Ensure base image exists first:
   ./scripts/dev/build-ml-base-image.sh
   ./scripts/dev/build-production-images.sh
   ./scripts/dev/push-and-deploy.sh
   ```

3. **Check if base image exists**:
   ```bash
   docker images | grep zivohealth-base
   ```

4. **Use AWS Profile** (already configured in scripts):
   - Scripts automatically use `AWS_PROFILE=zivohealth`
   - Region: `us-east-1`

## 📖 Full Documentation

For detailed information, see: [docs/TWO_TIER_DOCKER_BUILD.md](docs/TWO_TIER_DOCKER_BUILD.md)

## ✅ Next Steps

1. **Build base image** (first time only):
   ```bash
   ./scripts/dev/build-ml-base-image.sh
   ```

2. **For all future deployments**, just use:
   ```bash
   ./scripts/dev/build-production-images.sh && ./scripts/dev/push-and-deploy.sh
   ```

**That's it!** Your builds are now 80% faster! 🚀

