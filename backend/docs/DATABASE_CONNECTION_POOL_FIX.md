# Database Connection Pool Exhaustion Fix

## Problem Description

The application was experiencing `sqlalchemy.exc.TimeoutError: QueuePool limit of size 10 overflow 20 reached` errors during vitals data aggregation, causing API requests to timeout and fail.

### Error Details
```
sqlalchemy.exc.TimeoutError: QueuePool limit of size 10 overflow 20 reached, 
connection timed out, timeout 30.00
```

This error occurred when:
- Vitals/nutrition/lab data aggregation was running
- Multiple API requests were trying to authenticate users
- All 30 connections (10 base + 20 overflow) were exhausted
- New requests had to wait 30 seconds before timing out

## Root Causes

### 1. **Pool Size Too Small**
- **Before**: 10 base connections + 20 overflow = 30 total
- **Issue**: Not enough connections for concurrent API requests + background aggregation
- **Impact**: During aggregation, most connections were consumed, leaving none for API requests

### 2. **Long-Running Aggregation Operations**
- **Issue**: Aggregation processes held connections for extended periods (minutes)
- **Why**: Processing large batches (100-500 records) in single transactions
- **Impact**: Connections locked during complex aggregation operations (categorization, hourly, daily, weekly, monthly)

### 3. **Infrequent Commits**
- **Issue**: Aggregation held transactions open without intermediate commits
- **Why**: Processing entire batches before committing
- **Impact**: Database locks held unnecessarily long, blocking other operations

### 4. **Large Batch Sizes**
- **Issue**: Processing 100-500 records per batch
- **Why**: Trying to optimize throughput
- **Impact**: Each batch held a connection for too long

## Solutions Implemented

### 1. **Increased Connection Pool Size**
**File**: `backend/app/db/session.py`

```python
# BEFORE
pool_size=10,          # Base pool
max_overflow=20,       # Overflow connections
pool_timeout=30,       # 30 second timeout

# AFTER
pool_size=20,          # Increased from 10 to 20
max_overflow=30,       # Increased from 20 to 30
pool_timeout=45,       # Increased from 30 to 45 seconds
```

**Result**: Now supports up to **50 concurrent connections** (20 + 30) with longer timeout

### 2. **Reduced Batch Sizes**
**File**: `backend/app/core/background_worker.py`

```python
# BEFORE
self.batch_size = batch_size or 100
self.max_batch_size = 500

# AFTER
self.batch_size = batch_size or 50   # Reduced from 100
self.max_batch_size = 200            # Reduced from 500
```

**Result**: Smaller batches = shorter connection hold times = faster turnover

### 3. **Frequent Commits**
**File**: `backend/app/core/background_worker.py`

Added explicit commits after:
- Status updates (marking as "processing")
- Each user-date aggregation
- Error handling (marking as "failed")

```python
# Mark entries as processing
VitalsCRUD.mark_aggregation_processing(db, entry_ids)
db.commit()  # ✅ Commit immediately

# Process each user-date group
for (user_id, target_date), group_entries in user_date_groups.items():
    try:
        await self._perform_vitals_aggregation(db, user_id, target_date)
        db.commit()  # ✅ Commit after each group
    except Exception as e:
        db.rollback()  # ✅ Rollback on error
        # Mark as failed
        VitalsCRUD.mark_aggregation_failed(db, group_entry_ids, str(e))
        db.commit()  # ✅ Commit failure status
```

**Result**: Connections released faster, locks held for shorter periods

### 4. **Connection Pool Monitoring**
**File**: `backend/app/core/background_worker.py`

Added connection pool statistics logging:

```python
from app.core.database_utils import check_connection_pool_stats

# Before batch processing
pool_stats = check_connection_pool_stats()
logger.debug(f"🔌 Connection pool before batch: {pool_stats}")

# After batch processing
pool_stats_after = check_connection_pool_stats()
logger.debug(f"🔌 Connection pool after batch: {pool_stats_after}")
```

**Result**: Can monitor connection pool health in real-time

## Monitoring Connection Pool Health

### 1. **Check Connection Pool Status**

Use the utility function in your code:

```python
from app.core.database_utils import check_connection_pool_stats, log_connection_pool_status

# Get stats as dictionary
stats = check_connection_pool_stats()
print(stats)
# Output: {
#     'pool_size': 20,
#     'checked_in': 18,
#     'checked_out': 2,
#     'overflow': 0,
#     'invalid': 0,
#     'total_connections': 20,
#     'status': 'healthy'
# }

# Or just log the status
log_connection_pool_status()
```

### 2. **Monitor Logs**

Look for these log messages:

```bash
# Normal operation
🔌 [SmartWorker] Connection pool before batch: {'checked_out': 1, 'status': 'healthy'}

# Warning - pool exhausted
⚠️  Connection pool exhausted: {'checked_out': 50, 'status': 'exhausted'}
```

### 3. **Check PostgreSQL Connections**

On the database server:

```sql
-- See current connections
SELECT count(*) as connections, state 
FROM pg_stat_activity 
WHERE datname = 'zivohealth' 
GROUP BY state;

-- See connections by application
SELECT application_name, count(*) 
FROM pg_stat_activity 
WHERE datname = 'zivohealth' 
GROUP BY application_name;

-- Kill idle connections (if needed)
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE datname = 'zivohealth' 
AND state = 'idle' 
AND query_start < NOW() - INTERVAL '5 minutes';
```

## Best Practices Going Forward

### 1. **Always Use Context Managers for Database Sessions**

✅ **GOOD**:
```python
from app.core.database_utils import get_db_session

with get_db_session() as db:
    # Your database operations
    result = db.query(Model).all()
    # Session automatically closed and committed
```

❌ **BAD**:
```python
db = SessionLocal()
result = db.query(Model).all()
# Session never closed - LEAK!
```

### 2. **Commit Frequently in Long Operations**

✅ **GOOD**:
```python
for batch in large_dataset:
    process_batch(db, batch)
    db.commit()  # Commit after each batch
```

❌ **BAD**:
```python
for batch in large_dataset:
    process_batch(db, batch)
db.commit()  # Holding transaction for entire loop!
```

### 3. **Keep Batch Sizes Small**

✅ **GOOD**:
```python
batch_size = 50  # Small batches
for i in range(0, len(data), batch_size):
    batch = data[i:i+batch_size]
    process_batch(batch)
```

❌ **BAD**:
```python
batch_size = 1000  # Large batch holds connection too long
```

### 4. **Use Read-Only Connections for Queries**

For read-only operations, consider using connection pooling strategies:

```python
# For heavy read operations, use connection pool mode
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,  # Verify connections are alive
    pool_recycle=300     # Recycle connections every 5 minutes
)
```

### 5. **Monitor Connection Pool in Production**

Add a health check endpoint:

```python
@router.get("/health/db-pool")
def check_db_pool_health():
    from app.core.database_utils import check_connection_pool_stats
    stats = check_connection_pool_stats()
    
    if stats['status'] == 'exhausted':
        raise HTTPException(status_code=503, detail="Database pool exhausted")
    
    return stats
```

## Performance Impact

### Before Fix
- ❌ Connection pool: 10 + 20 = 30 connections
- ❌ Batch size: 100-500 records
- ❌ Timeout errors during aggregation
- ❌ API requests blocked for 30+ seconds

### After Fix
- ✅ Connection pool: 20 + 30 = 50 connections (+67% capacity)
- ✅ Batch size: 50-200 records (faster turnover)
- ✅ Frequent commits (shorter lock times)
- ✅ Connection pool monitoring
- ✅ API requests continue during aggregation

## Testing the Fix

### 1. **Monitor During Aggregation**

```bash
# Watch the logs during vitals aggregation
tail -f backend/logs/server.log | grep "Connection pool"

# You should see:
# 🔌 [SmartWorker] Connection pool before batch: {'checked_out': 1, 'status': 'healthy'}
# 🔌 [SmartWorker] Connection pool after batch: {'checked_out': 1, 'status': 'healthy'}
```

### 2. **Load Test**

```python
import asyncio
import aiohttp

async def make_request():
    async with aiohttp.ClientSession() as session:
        async with session.get('http://localhost:8000/api/v1/vitals/data') as resp:
            return resp.status

async def load_test():
    tasks = [make_request() for _ in range(50)]
    results = await asyncio.gather(*tasks)
    print(f"Success rate: {results.count(200)}/50")

# Run while aggregation is happening
asyncio.run(load_test())
```

### 3. **Check for Timeouts**

```bash
# Should see no more TimeoutError messages
grep "TimeoutError" backend/logs/server.log

# Before fix: Multiple timeout errors
# After fix: No timeout errors
```

## Rollback Plan

If issues arise, revert changes:

```bash
cd backend
git diff app/db/session.py
git checkout app/db/session.py

git diff app/core/background_worker.py
git checkout app/core/background_worker.py

# Restart services
./scripts/restart_server.sh
```

## Additional Optimizations (Future)

### 1. **Separate Database Pools**
Consider separate pools for API vs. background workers:

```python
# API pool - optimized for many short requests
api_engine = create_engine(DATABASE_URL, pool_size=30, max_overflow=20)

# Worker pool - optimized for long-running operations
worker_engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=5)
```

### 2. **Read Replicas**
Use read replicas for heavy aggregation queries:

```python
# Write to primary
engine_primary = create_engine(PRIMARY_DATABASE_URL)

# Read from replica
engine_replica = create_engine(REPLICA_DATABASE_URL)
```

### 3. **Connection Pooler (PgBouncer)**
Add PgBouncer for connection pooling at PostgreSQL level:

```bash
# Install PgBouncer
sudo apt-get install pgbouncer

# Configure for transaction pooling
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 20
```

### 4. **Async Database Drivers**
Consider using async SQLAlchemy for better concurrency:

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/db",
    pool_size=20,
    max_overflow=30
)
```

## Summary

The connection pool exhaustion issue was caused by:
1. Pool too small (30 connections)
2. Large batches holding connections too long
3. Infrequent commits holding transactions open

Fixed by:
1. ✅ Increased pool to 50 connections (+67%)
2. ✅ Reduced batch sizes from 100-500 to 50-200
3. ✅ Added frequent commits after each operation
4. ✅ Added connection pool monitoring

**Result**: System now handles concurrent API requests and background aggregation without connection exhaustion.

## Related Files

- `backend/app/db/session.py` - Database connection pool configuration
- `backend/app/core/background_worker.py` - Aggregation worker with optimized batching
- `backend/app/core/database_utils.py` - Database utilities and monitoring
- `backend/app/api/deps.py` - API dependency injection (session management)
- `backend/docs/DATABASE_CONNECTION_POOL_FIX.md` - This documentation

## Contact

For questions or issues related to database connection pool management, refer to this documentation or contact the backend team.

