# Health Score Deployment in Docker Container

## 🐳 Container Deployment Guide

### Prerequisites

- Scripts are copied to container (usually in `/app/backend/scripts/`)
- Container has access to production database
- Virtual environment activated in container

---

## Method 1: Exec into Running Container

### Step 1: Connect to Container

```bash
# Find your container name/ID
docker ps | grep backend

# Exec into the container
docker exec -it <container_name> bash

# OR for ECS/Fargate
aws ecs execute-command \
  --cluster your-cluster \
  --task your-task-id \
  --container backend \
  --interactive \
  --command "/bin/bash"
```

### Step 2: Run Scripts Inside Container

```bash
# Navigate to backend directory
cd /app/backend

# Activate virtual environment (if needed)
source /app/venv/bin/activate  # Adjust path as needed

# Step 1: Add metric anchors
python scripts/add_health_score_anchors.py

# Step 2: Backfill sleep data
python scripts/backfill_sleep_duration.py

# Step 3: Recalculate scores
python scripts/recalculate_health_scores.py --all-users --days 30
```

---

## Method 2: Docker Run Command (One-off)

### From Host Machine

```bash
# Add metric anchors
docker exec <container_name> \
  python /app/backend/scripts/add_health_score_anchors.py

# Backfill sleep data
docker exec <container_name> \
  python /app/backend/scripts/backfill_sleep_duration.py

# Recalculate health scores
docker exec <container_name> \
  python /app/backend/scripts/recalculate_health_scores.py \
  --all-users --days 30
```

### With Custom Python Path

```bash
# If Python path is different
docker exec <container_name> \
  /app/venv/bin/python /app/backend/scripts/add_health_score_anchors.py
```

---

## Method 3: SQL Scripts (Database Direct)

**Best for production:** Connect to RDS/database directly, no container needed.

```bash
# From host machine or bastion
psql -h your-rds-endpoint.amazonaws.com \
     -U your_db_user \
     -d your_database \
     -f backend/scripts/sql/01_add_metric_anchors.sql

psql -h your-rds-endpoint.amazonaws.com \
     -U your_db_user \
     -d your_database \
     -f backend/scripts/sql/02_backfill_sleep_duration.sql
```

**Pros:**
- ✅ No need to access container
- ✅ Direct database connection
- ✅ Faster for bulk operations
- ✅ Can run from any machine with DB access

---

## Method 4: Docker Compose

If using docker-compose:

```bash
# Run script in backend service
docker-compose exec backend python scripts/add_health_score_anchors.py

docker-compose exec backend python scripts/backfill_sleep_duration.py

docker-compose exec backend python scripts/recalculate_health_scores.py \
  --all-users --days 30
```

---

## Method 5: Kubernetes/ECS Task

### Create One-off Task

```bash
# For ECS - run as one-off task
aws ecs run-task \
  --cluster your-cluster \
  --task-definition your-backend-task \
  --overrides '{
    "containerOverrides": [{
      "name": "backend",
      "command": [
        "python",
        "/app/backend/scripts/recalculate_health_scores.py",
        "--all-users",
        "--days",
        "30"
      ]
    }]
  }'

# For Kubernetes - run as Job
kubectl run health-score-recalc \
  --image=your-backend-image \
  --restart=Never \
  --command -- python /app/backend/scripts/recalculate_health_scores.py \
  --all-users --days 30
```

---

## Environment Variables in Container

### Check Database Connection

```bash
# Inside container
echo $DATABASE_URL
echo $POSTGRES_SERVER
echo $POSTGRES_DB

# Test database connection
psql $DATABASE_URL -c "SELECT version();"

# Or with Python
python -c "from app.db.session import engine; print(engine.url)"
```

### Set Environment Variables (if needed)

```bash
# For docker exec
docker exec -e DATABASE_URL="postgresql://..." \
  <container_name> \
  python /app/backend/scripts/add_health_score_anchors.py

# For docker-compose
docker-compose exec \
  -e DATABASE_URL="postgresql://..." \
  backend python scripts/add_health_score_anchors.py
```

---

## Common Container Paths

Depending on your setup, scripts might be at:

```bash
/app/backend/scripts/               # Common
/opt/backend/scripts/               # Alternative
/usr/src/app/backend/scripts/       # Alternative
/code/backend/scripts/              # Alternative
```

**Find the correct path:**

```bash
docker exec <container> find / -name "add_health_score_anchors.py" 2>/dev/null
```

---

## Verification Inside Container

```bash
# Check scripts exist
docker exec <container> ls -la /app/backend/scripts/*.py

# Check database connectivity
docker exec <container> python -c "
from app.db.session import SessionLocal
db = SessionLocal()
print('✓ Database connected')
db.close()
"

# Check metric anchors
docker exec <container> python -c "
from app.db.session import SessionLocal
from app.health_scoring.models import MetricAnchorRegistry
db = SessionLocal()
count = db.query(MetricAnchorRegistry).filter(MetricAnchorRegistry.active == True).count()
print(f'Active anchors: {count}')
db.close()
"
```

---

## Production Deployment Checklist

### Before Running

- [ ] Database backup completed
- [ ] Confirmed container has access to production DB
- [ ] Tested script on staging/dev container first
- [ ] Confirmed scripts are copied to container
- [ ] Checked available disk space in container
- [ ] Verified Python dependencies are installed

### Execution Order

```bash
# 1. Add metric anchors (fast, < 5 seconds)
docker exec <container> python /app/backend/scripts/add_health_score_anchors.py

# 2. Backfill sleep data (medium, 1-5 minutes)
docker exec <container> python /app/backend/scripts/backfill_sleep_duration.py

# 3. Test with one user first
docker exec <container> python /app/backend/scripts/recalculate_health_scores.py \
  --user-id 1 --days 7

# 4. Recalculate all (slow, 5-30+ minutes)
docker exec <container> python /app/backend/scripts/recalculate_health_scores.py \
  --all-users --days 30
```

### After Running

- [ ] Verify metric anchors added (SQL query)
- [ ] Verify sleep duration_minutes populated
- [ ] Check health scores are non-zero
- [ ] Monitor application logs for errors
- [ ] Verify API responses include scores

---

## Troubleshooting Container Issues

### Issue: Script not found

```bash
# Find script location
docker exec <container> find / -name "*.py" -path "*/scripts/*" 2>/dev/null

# Check working directory
docker exec <container> pwd

# List scripts directory
docker exec <container> ls -la /app/backend/scripts/
```

### Issue: Permission denied

```bash
# Check file permissions
docker exec <container> ls -la /app/backend/scripts/*.py

# Run as root if needed
docker exec --user root <container> \
  python /app/backend/scripts/add_health_score_anchors.py
```

### Issue: Module not found

```bash
# Check Python path
docker exec <container> python -c "import sys; print('\n'.join(sys.path))"

# Check if modules installed
docker exec <container> pip list | grep -i sqlalchemy

# Ensure in correct directory
docker exec <container> bash -c "cd /app/backend && python scripts/add_health_score_anchors.py"
```

### Issue: Database connection failed

```bash
# Check environment variables
docker exec <container> env | grep -i postgres

# Test connection
docker exec <container> psql $DATABASE_URL -c "SELECT 1;"

# Check if database is reachable
docker exec <container> ping -c 3 your-db-host
```

### Issue: Out of memory

```bash
# Check container memory
docker stats <container>

# Process in smaller batches
docker exec <container> python /app/backend/scripts/recalculate_health_scores.py \
  --all-users --days 30 --limit-users 50

# Or use SQL scripts (more memory efficient)
psql -h your-db -d your_database -f scripts/sql/02_backfill_sleep_duration.sql
```

---

## Monitoring Long-Running Scripts

### Run in Background

```bash
# Using nohup
docker exec <container> bash -c \
  "nohup python /app/backend/scripts/recalculate_health_scores.py \
   --all-users --days 30 > /tmp/recalc.log 2>&1 &"

# Check progress
docker exec <container> tail -f /tmp/recalc.log

# Check if still running
docker exec <container> ps aux | grep recalculate
```

### Using Screen/Tmux (if available)

```bash
# Start screen session
docker exec -it <container> screen

# Run script
python /app/backend/scripts/recalculate_health_scores.py --all-users --days 30

# Detach: Ctrl+A, D
# Reattach: docker exec -it <container> screen -r
```

---

## Alternative: Run Scripts from CI/CD

### GitHub Actions Example

```yaml
name: Update Health Score Metrics

on:
  workflow_dispatch:  # Manual trigger

jobs:
  update-metrics:
    runs-on: ubuntu-latest
    steps:
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Run metric update in ECS
        run: |
          aws ecs run-task \
            --cluster prod-cluster \
            --task-definition backend-task \
            --overrides '{
              "containerOverrides": [{
                "name": "backend",
                "command": ["python", "/app/backend/scripts/add_health_score_anchors.py"]
              }]
            }'
```

---

## Quick Reference Commands

```bash
# === BASIC ===
# Connect to container
docker exec -it <container> bash

# Run script
docker exec <container> python /app/backend/scripts/add_health_score_anchors.py

# === FULL DEPLOYMENT ===
# All three steps
docker exec <container> python /app/backend/scripts/add_health_score_anchors.py && \
docker exec <container> python /app/backend/scripts/backfill_sleep_duration.py && \
docker exec <container> python /app/backend/scripts/recalculate_health_scores.py --all-users --days 30

# === VERIFICATION ===
# Check database
docker exec <container> psql $DATABASE_URL -c \
  "SELECT COUNT(*) FROM metric_anchor_registry WHERE active = true;"

# Check health scores
docker exec <container> psql $DATABASE_URL -c \
  "SELECT COUNT(*) FROM health_score_results_daily WHERE date >= CURRENT_DATE - INTERVAL '7 days';"
```

---

## Best Practice Recommendations

1. **Use SQL scripts for initial data updates** (anchors, backfill)
   - Faster
   - No container access needed
   - Direct database connection

2. **Use Python script for recalculation**
   - Better error handling
   - Progress tracking
   - Easier to monitor

3. **Test on staging first**
   - Run scripts on staging container
   - Verify results
   - Then deploy to production

4. **Monitor during execution**
   - Watch container logs
   - Monitor database CPU/connections
   - Check application health

5. **Run during off-peak hours**
   - Less impact on users
   - More database resources available
   - Easier to troubleshoot if issues occur

---

## Support

For issues specific to your container setup:
1. Check container logs: `docker logs <container>`
2. Verify environment variables
3. Test database connectivity
4. Check Python dependencies
5. Verify file permissions

All scripts are designed to be safe and idempotent - they can be run multiple times without causing issues.

