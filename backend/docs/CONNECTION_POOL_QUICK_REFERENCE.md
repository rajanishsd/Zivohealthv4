# Database Connection Pool - Quick Reference

## Quick Diagnosis

### Is the pool exhausted?

```python
from app.core.database_utils import check_connection_pool_stats

stats = check_connection_pool_stats()
print(stats)
```

**Healthy Output:**
```python
{
    'pool_size': 20,
    'checked_in': 18,    # Most connections available
    'checked_out': 2,    # Few connections in use
    'overflow': 0,       # No overflow needed
    'status': 'healthy'
}
```

**Exhausted Output:**
```python
{
    'pool_size': 20,
    'checked_in': 0,     # No connections available
    'checked_out': 48,   # Using base + overflow
    'overflow': 28,      # Using almost all overflow
    'status': 'exhausted'  # ⚠️ PROBLEM!
}
```

## Current Configuration

### Connection Pool Settings
| Setting | Value | Purpose |
|---------|-------|---------|
| `pool_size` | 20 | Base connections (increased from 10) |
| `max_overflow` | 30 | Burst capacity (increased from 20) |
| `pool_timeout` | 45s | Wait time (increased from 30s) |
| `pool_recycle` | 300s | Recycle after 5 min |
| `pool_pre_ping` | True | Verify before use |
| **Total Capacity** | **50** | **20 + 30** |

### Worker Batch Settings
| Setting | Value | Purpose |
|---------|-------|---------|
| `batch_size` | 50 | Records per batch (reduced from 100) |
| `max_batch_size` | 200 | Maximum batch (reduced from 500) |
| `delay_seconds` | 30 | Wait before aggregation |

## Common Issues & Solutions

### Issue: "QueuePool limit reached, connection timed out"

**Symptoms:**
- API requests timeout
- Users can't authenticate
- Aggregation running

**Immediate Fix:**
```bash
# Restart API server to reset pool
./scripts/restart_server.sh

# Check if aggregation is stuck
ps aux | grep worker_process

# If stuck, kill it
pkill -f worker_process
```

**Root Cause:** Long-running aggregation holding too many connections

**Permanent Fix:** Already implemented - smaller batches + frequent commits

### Issue: "Too many connections" from PostgreSQL

**Symptoms:**
- PostgreSQL rejects new connections
- Error: "FATAL: sorry, too many clients already"

**Check PostgreSQL limit:**
```sql
SHOW max_connections;  -- Default: 100
```

**See current connections:**
```sql
SELECT count(*) FROM pg_stat_activity WHERE datname = 'zivohealth';
```

**Solution:**
```sql
-- Increase PostgreSQL max_connections
ALTER SYSTEM SET max_connections = 200;
-- Restart PostgreSQL
```

### Issue: Slow aggregation

**Symptoms:**
- Aggregation takes forever
- Connections held for minutes
- API requests slow during aggregation

**Check batch sizes:**
```python
# In background_worker.py
# Should be:
self.batch_size = 50
self.max_batch_size = 200

# NOT:
self.batch_size = 500  # Too large!
```

**Solution:** Already fixed - batch sizes reduced

## Monitoring Commands

### 1. Check Connection Pool in Python

```python
from app.core.database_utils import log_connection_pool_status

# Log current status
log_connection_pool_status()
```

### 2. Check PostgreSQL Connections

```bash
# SSH to database server
ssh your-db-server

# Connect to PostgreSQL
sudo -u postgres psql

# Run monitoring queries
```

```sql
-- Active connections by state
SELECT 
    state, 
    count(*) 
FROM pg_stat_activity 
WHERE datname = 'zivohealth' 
GROUP BY state;

-- Long-running queries
SELECT 
    pid,
    now() - query_start AS duration,
    state,
    query
FROM pg_stat_activity
WHERE state != 'idle'
AND now() - query_start > interval '30 seconds'
ORDER BY duration DESC;

-- Kill specific connection (if needed)
SELECT pg_terminate_backend(12345);  -- Replace with actual PID
```

### 3. Monitor API Response Times

```bash
# Watch API logs for slow requests
tail -f backend/logs/server.log | grep -E "(slow|timeout|QueuePool)"

# Count errors
grep "TimeoutError" backend/logs/server.log | wc -l
```

### 4. Monitor Worker Progress

```bash
# Watch worker logs
tail -f backend/aggregation/worker.log

# Should see frequent commits:
# ✅ Completed vitals aggregation for user 123
# 🔌 Connection pool after batch: {'checked_out': 1}
```

## Best Practices Checklist

### ✅ When Writing Database Code

- [ ] Use `get_db_session()` context manager
- [ ] Commit after each batch in loops
- [ ] Keep batch sizes small (< 100 records)
- [ ] Add rollback on exceptions
- [ ] Close sessions explicitly if not using context manager

### ✅ When Running Aggregation

- [ ] Check connection pool before starting
- [ ] Monitor logs during execution
- [ ] Verify API still responds
- [ ] Check pool stats after completion

### ✅ When Deploying Changes

- [ ] Test with realistic data volumes
- [ ] Monitor connection pool during test
- [ ] Verify no timeout errors
- [ ] Load test API during aggregation

## Emergency Procedures

### Procedure 1: Pool Exhausted - API Down

```bash
# 1. Restart API server
./scripts/restart_server.sh

# 2. Check if worker is running
ps aux | grep worker_process

# 3. If worker running, let it finish
# If stuck, kill it:
pkill -f worker_process

# 4. Monitor recovery
tail -f backend/logs/server.log
```

### Procedure 2: PostgreSQL Connection Limit Reached

```bash
# 1. SSH to database server
ssh your-db-server

# 2. Check connections
sudo -u postgres psql -c "SELECT count(*) FROM pg_stat_activity;"

# 3. Kill idle connections
sudo -u postgres psql << EOF
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE datname = 'zivohealth' 
AND state = 'idle' 
AND query_start < NOW() - INTERVAL '5 minutes';
EOF

# 4. Restart app servers
./scripts/restart_server.sh
```

### Procedure 3: Stuck Aggregation

```bash
# 1. Check if worker is stuck
ps aux | grep worker_process

# 2. Check worker logs for errors
tail -100 backend/aggregation/worker.log

# 3. Kill stuck worker
pkill -f worker_process

# 4. Check database for pending records
sudo -u postgres psql zivohealth << EOF
SELECT 
    'vitals' as type,
    aggregation_status,
    count(*) 
FROM vitals_raw_data 
GROUP BY aggregation_status
UNION ALL
SELECT 
    'nutrition' as type,
    aggregation_status,
    count(*) 
FROM nutrition_raw_data 
GROUP BY aggregation_status;
EOF

# 5. Restart worker if needed
./scripts/start_worker.sh  # If you have this script
```

## Configuration Files

### Main Configuration
- **Pool Settings**: `backend/app/db/session.py`
- **Worker Settings**: `backend/app/core/background_worker.py`
- **Monitoring**: `backend/app/core/database_utils.py`

### To Change Pool Size

Edit `backend/app/db/session.py`:
```python
engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    pool_size=20,        # ← Change this
    max_overflow=30,     # ← Change this
    pool_timeout=45,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=False
)
```

Restart server after changes:
```bash
./scripts/restart_server.sh
```

### To Change Batch Size

Edit `backend/app/core/background_worker.py`:
```python
def __init__(self, batch_size: int = None, ...):
    self.batch_size = batch_size or 50  # ← Change this
    self.max_batch_size = 200           # ← Change this
```

No restart needed (used on next aggregation run)

## Alerting Setup (Optional)

### Set up alerts for pool exhaustion:

```python
# In your monitoring code
from app.core.database_utils import check_connection_pool_stats

def check_pool_health():
    stats = check_connection_pool_stats()
    
    # Alert if > 80% used
    usage_percent = (stats['checked_out'] / (stats['pool_size'] + stats['overflow'])) * 100
    
    if usage_percent > 80:
        send_alert(f"Connection pool {usage_percent}% exhausted!")
    
    if stats['status'] == 'exhausted':
        send_critical_alert("Connection pool fully exhausted!")
```

## Performance Metrics

### Expected Performance After Fix

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Pool Capacity | 30 | 50 | +67% |
| Batch Size | 100-500 | 50-200 | -50% |
| Connection Hold Time | 30-120s | 10-30s | -75% |
| Timeout Rate | High | Low | -95% |
| API Response During Aggregation | Slow/Timeout | Normal | ✅ |

### Targets

- ✅ Connection pool usage < 80% during normal operation
- ✅ Connection pool usage < 95% during aggregation peaks
- ✅ Zero timeout errors
- ✅ API response time < 200ms (not including database query time)
- ✅ Aggregation completes without blocking API

## Further Reading

- [Full Documentation](./DATABASE_CONNECTION_POOL_FIX.md)
- [SQLAlchemy Connection Pooling](https://docs.sqlalchemy.org/en/14/core/pooling.html)
- [PostgreSQL Connection Management](https://www.postgresql.org/docs/current/runtime-config-connection.html)

## Questions?

Contact the backend team or refer to the full documentation:
- `backend/docs/DATABASE_CONNECTION_POOL_FIX.md` - Detailed fix documentation
- `backend/docs/CONNECTION_POOL_QUICK_REFERENCE.md` - This quick reference

