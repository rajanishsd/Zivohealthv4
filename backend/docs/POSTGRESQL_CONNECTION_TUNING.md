# PostgreSQL Connection Tuning Guide

This guide complements the application-level connection pool fixes by optimizing PostgreSQL server settings.

## Current Application Settings

**Application Pool (per instance):**
- Pool Size: 20 connections
- Max Overflow: 30 connections
- Total per instance: **50 connections**

**If running multiple instances:**
- 3 instances × 50 = **150 total connections**
- Plus worker processes: +10-20 connections
- **Total needed: ~170 connections**

## PostgreSQL Configuration

### 1. Check Current Settings

```sql
-- Connect to PostgreSQL
sudo -u postgres psql zivohealth

-- Check current connection limit
SHOW max_connections;
-- Default: 100 (probably too low)

-- Check current active connections
SELECT count(*) FROM pg_stat_activity;

-- Check connections by application
SELECT 
    application_name,
    state,
    count(*) 
FROM pg_stat_activity 
GROUP BY application_name, state;
```

### 2. Recommended Settings

Edit PostgreSQL configuration file:

```bash
# Find config file
sudo -u postgres psql -c "SHOW config_file;"
# Typical locations:
# /etc/postgresql/14/main/postgresql.conf
# /var/lib/postgresql/data/postgresql.conf

# Edit config
sudo nano /etc/postgresql/14/main/postgresql.conf
```

**Recommended Changes:**

```conf
# CONNECTION SETTINGS
# ---------------------------------

# Increase max connections (default: 100)
# Set to 2-3x your application pool total
max_connections = 200                   # Changed from 100

# Reserve connections for superuser/admin
superuser_reserved_connections = 5      # Keep default

# CONNECTION POOLING (if using PgBouncer)
# max_connections = 100                  # Lower if using PgBouncer
# (PgBouncer handles the pooling)


# RESOURCE USAGE (Memory)
# ---------------------------------

# More connections = more memory needed
# Each connection uses ~10MB base + working memory

# Shared buffers - typically 25% of RAM
shared_buffers = 2GB                    # Adjust based on your RAM

# Effective cache - PostgreSQL's view of available memory
# Typically 50-75% of RAM
effective_cache_size = 6GB              # Adjust based on your RAM

# Work memory per operation (sort, hash, etc.)
# Formula: (Total RAM × 0.25) / max_connections
work_mem = 10MB                         # Adjust based on your workload

# Maintenance work memory (vacuum, index creation)
maintenance_work_mem = 256MB            # Can be higher


# WRITE AHEAD LOG (Performance)
# ---------------------------------

# Increase for better write performance
wal_buffers = 16MB
max_wal_size = 2GB
min_wal_size = 1GB


# QUERY PLANNER
# ---------------------------------

# More connections = need better query planning
random_page_cost = 1.1                  # Lower for SSDs (default: 4.0)
effective_io_concurrency = 200          # Higher for SSDs (default: 1)


# LOGGING (for monitoring)
# ---------------------------------

# Log slow queries
log_min_duration_statement = 1000       # Log queries > 1 second

# Log connections and disconnections
log_connections = on
log_disconnections = on

# Log lock waits
log_lock_waits = on
deadlock_timeout = 1s
```

### 3. Apply Configuration Changes

```bash
# Check config syntax
sudo -u postgres /usr/lib/postgresql/14/bin/postgres -D /var/lib/postgresql/14/main --check

# Restart PostgreSQL (brief downtime)
sudo systemctl restart postgresql

# Or reload (no downtime, but not all settings apply)
sudo systemctl reload postgresql
sudo -u postgres psql -c "SELECT pg_reload_conf();"

# Verify new settings
sudo -u postgres psql -c "SHOW max_connections;"
# Should show: 200
```

## Memory Calculation

### Formula

```
Total Memory Needed = 
    shared_buffers 
    + (max_connections × (work_mem + temp_buffers))
    + (max_connections × 10MB)  # Base per-connection overhead
    + OS overhead (~1-2GB)
```

### Example: 16GB RAM Server

```
Recommended settings:
- shared_buffers: 4GB (25% of RAM)
- max_connections: 200
- work_mem: 10MB
- temp_buffers: 8MB (default)

Calculation:
= 4GB 
+ (200 × 18MB) 
+ (200 × 10MB) 
+ 2GB
= 4GB + 3.6GB + 2GB + 2GB
= 11.6GB

Available for OS and caching: 16GB - 11.6GB = 4.4GB ✅
```

### Example: 8GB RAM Server (Smaller)

```
Recommended settings:
- shared_buffers: 2GB (25% of RAM)
- max_connections: 150
- work_mem: 8MB
- temp_buffers: 8MB (default)

Calculation:
= 2GB 
+ (150 × 16MB)
+ (150 × 10MB)
+ 1.5GB
= 2GB + 2.4GB + 1.5GB + 1.5GB
= 7.4GB

Available for OS and caching: 8GB - 7.4GB = 0.6GB ✅ (tight but OK)
```

## Connection Pooler: PgBouncer (Optional)

If you need **even more connections**, use PgBouncer as an intermediary pooler.

### Benefits
- Application can have 500+ connections
- PostgreSQL only sees 50-100 actual connections
- Better resource management
- Connection pooling at database level

### Installation

```bash
# Install PgBouncer
sudo apt-get update
sudo apt-get install pgbouncer

# Configure
sudo nano /etc/pgbouncer/pgbouncer.ini
```

### PgBouncer Configuration

```ini
[databases]
zivohealth = host=localhost port=5432 dbname=zivohealth

[pgbouncer]
# Connection pooling mode
pool_mode = transaction              # Best for most apps
# pool_mode = session                # If app needs session state

# Pooling limits
max_client_conn = 1000               # Client connections PgBouncer accepts
default_pool_size = 50               # Actual PostgreSQL connections
reserve_pool_size = 10
reserve_pool_timeout = 5

# Connection limits per user
max_user_connections = 100

# Server connection behavior
server_idle_timeout = 600
server_lifetime = 3600

# Authentication
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt

# Listening address
listen_addr = 0.0.0.0
listen_port = 6432                   # PgBouncer port (not PostgreSQL 5432)

# Admin interface
admin_users = postgres
stats_users = postgres

# Logging
log_connections = 1
log_disconnections = 1
```

### Application Configuration with PgBouncer

Change your `.env` or database URL:

```bash
# Before (direct to PostgreSQL)
DATABASE_URL=postgresql://user:pass@localhost:5432/zivohealth

# After (through PgBouncer)
DATABASE_URL=postgresql://user:pass@localhost:6432/zivohealth
#                                              ^^^^
#                                         PgBouncer port
```

**PostgreSQL Settings with PgBouncer:**

```conf
# Can lower max_connections since PgBouncer manages the pool
max_connections = 100                 # Lower than before

# Adjust work_mem accordingly
work_mem = 20MB                       # Can be higher now
```

### Start PgBouncer

```bash
# Start service
sudo systemctl start pgbouncer
sudo systemctl enable pgbouncer

# Check status
sudo systemctl status pgbouncer

# Monitor PgBouncer
psql -h localhost -p 6432 -U postgres pgbouncer -c "SHOW POOLS;"
psql -h localhost -p 6432 -U postgres pgbouncer -c "SHOW STATS;"
```

## Monitoring Queries

### 1. Connection Count by State

```sql
SELECT 
    state,
    count(*) 
FROM pg_stat_activity 
WHERE datname = 'zivohealth' 
GROUP BY state;

-- Expected output:
--  state  | count
-- --------+-------
--  active |    12
--  idle   |    38
```

### 2. Connections by Application

```sql
SELECT 
    application_name,
    count(*) as connections,
    max(now() - state_change) as max_idle_time
FROM pg_stat_activity 
WHERE datname = 'zivohealth'
GROUP BY application_name;

-- Shows which apps are using connections
```

### 3. Long-Running Queries

```sql
SELECT 
    pid,
    usename,
    application_name,
    now() - query_start AS duration,
    state,
    LEFT(query, 100) as query_preview
FROM pg_stat_activity
WHERE 
    state != 'idle'
    AND now() - query_start > interval '10 seconds'
ORDER BY duration DESC;

-- Shows queries running > 10 seconds
```

### 4. Connection Limits

```sql
SELECT 
    count(*) as current_connections,
    (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') as max_connections,
    (SELECT setting::int FROM pg_settings WHERE name = 'superuser_reserved_connections') as reserved,
    (
        (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') - 
        (SELECT setting::int FROM pg_settings WHERE name = 'superuser_reserved_connections')
    ) as available_for_apps,
    count(*) * 100.0 / (
        (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') - 
        (SELECT setting::int FROM pg_settings WHERE name = 'superuser_reserved_connections')
    ) as usage_percent
FROM pg_stat_activity;

-- Shows connection usage percentage
```

### 5. Idle Connections (Potential Leaks)

```sql
SELECT 
    pid,
    usename,
    application_name,
    client_addr,
    now() - state_change AS idle_duration,
    query
FROM pg_stat_activity
WHERE 
    state = 'idle'
    AND now() - state_change > interval '5 minutes'
ORDER BY idle_duration DESC;

-- Connections idle > 5 minutes (potential leaks)
```

### 6. Kill Idle Connections

```sql
-- Kill specific connection
SELECT pg_terminate_backend(12345);  -- Replace with PID

-- Kill all idle connections > 10 minutes
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE 
    datname = 'zivohealth'
    AND state = 'idle'
    AND now() - state_change > interval '10 minutes';
```

## Alerting Setup

### Create Monitoring Function

```sql
CREATE OR REPLACE FUNCTION check_connection_health()
RETURNS TABLE (
    metric TEXT,
    current_value NUMERIC,
    threshold NUMERIC,
    status TEXT
) AS $$
BEGIN
    -- Current connections
    RETURN QUERY
    SELECT 
        'total_connections'::TEXT,
        count(*)::NUMERIC,
        (SELECT setting::NUMERIC FROM pg_settings WHERE name = 'max_connections') * 0.8,
        CASE 
            WHEN count(*) > (SELECT setting::INT FROM pg_settings WHERE name = 'max_connections') * 0.8 
            THEN 'WARNING'
            ELSE 'OK'
        END::TEXT
    FROM pg_stat_activity;
    
    -- Idle connections
    RETURN QUERY
    SELECT 
        'idle_connections'::TEXT,
        count(*)::NUMERIC,
        50::NUMERIC,
        CASE 
            WHEN count(*) > 50 THEN 'WARNING'
            ELSE 'OK'
        END::TEXT
    FROM pg_stat_activity
    WHERE state = 'idle' AND now() - state_change > interval '5 minutes';
    
    -- Long-running queries
    RETURN QUERY
    SELECT 
        'long_queries'::TEXT,
        count(*)::NUMERIC,
        5::NUMERIC,
        CASE 
            WHEN count(*) > 5 THEN 'WARNING'
            ELSE 'OK'
        END::TEXT
    FROM pg_stat_activity
    WHERE state != 'idle' AND now() - query_start > interval '30 seconds';
END;
$$ LANGUAGE plpgsql;

-- Use it
SELECT * FROM check_connection_health();
```

### Automated Monitoring Script

```bash
#!/bin/bash
# Save as: /usr/local/bin/check_db_connections.sh

THRESHOLD=160  # 80% of max_connections (200)

CURRENT=$(sudo -u postgres psql -t zivohealth -c "SELECT count(*) FROM pg_stat_activity;")

if [ "$CURRENT" -gt "$THRESHOLD" ]; then
    echo "WARNING: Database connections high: $CURRENT / 200"
    # Send alert (email, Slack, etc.)
    # mail -s "DB Connection Alert" admin@example.com <<< "Connections: $CURRENT"
fi
```

**Add to cron:**

```bash
# Check every 5 minutes
*/5 * * * * /usr/local/bin/check_db_connections.sh
```

## Performance Testing

### 1. Connection Stress Test

```python
import psycopg2
import concurrent.futures
import time

def create_connection():
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="zivohealth",
            user="your_user",
            password="your_password"
        )
        time.sleep(5)  # Hold connection for 5 seconds
        conn.close()
        return True
    except Exception as e:
        return str(e)

# Try to create 180 concurrent connections
with concurrent.futures.ThreadPoolExecutor(max_workers=180) as executor:
    results = list(executor.map(create_connection, range(180)))

success = results.count(True)
failures = len(results) - success

print(f"Success: {success}/180")
print(f"Failures: {failures}/180")

# With max_connections=200, should succeed
# With max_connections=100, some will fail
```

### 2. Query Performance Under Load

```sql
-- Create test table
CREATE TABLE connection_test (
    id SERIAL PRIMARY KEY,
    data TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Simulate load
DO $$
DECLARE
    i INT;
BEGIN
    FOR i IN 1..1000 LOOP
        INSERT INTO connection_test (data) VALUES ('Test ' || i);
    END LOOP;
END $$;

-- Test query performance
EXPLAIN ANALYZE
SELECT * FROM connection_test WHERE data LIKE '%Test%';
```

## Troubleshooting

### Issue: "FATAL: remaining connection slots are reserved"

**Cause:** Hit `superuser_reserved_connections` limit

**Solution:**
```sql
-- Increase max_connections
ALTER SYSTEM SET max_connections = 200;
-- Restart PostgreSQL
```

### Issue: "FATAL: sorry, too many clients already"

**Cause:** Reached `max_connections` limit

**Solutions:**
1. Kill idle connections (see above)
2. Increase `max_connections`
3. Implement PgBouncer
4. Fix application connection leaks

### Issue: Out of Memory

**Cause:** `max_connections` too high for available RAM

**Solution:**
```sql
-- Reduce max_connections
ALTER SYSTEM SET max_connections = 150;

-- Or reduce work_mem
ALTER SYSTEM SET work_mem = '5MB';

-- Restart PostgreSQL
```

### Issue: Slow Queries Under High Connection Load

**Cause:** Resource contention

**Solution:**
```sql
-- Increase work_mem (but watch total memory!)
ALTER SYSTEM SET work_mem = '16MB';

-- Increase shared_buffers
ALTER SYSTEM SET shared_buffers = '4GB';

-- Use connection pooler (PgBouncer)
```

## Checklist

### PostgreSQL Server Tuning
- [ ] Increase `max_connections` to 200
- [ ] Adjust `shared_buffers` based on RAM
- [ ] Configure `work_mem` appropriately
- [ ] Enable query logging for slow queries
- [ ] Enable connection logging
- [ ] Set up monitoring queries
- [ ] Test configuration with stress test
- [ ] Monitor for 24 hours after changes

### Optional: PgBouncer Setup
- [ ] Install PgBouncer
- [ ] Configure connection pooling
- [ ] Update application DATABASE_URL
- [ ] Test with application
- [ ] Monitor PgBouncer stats

### Monitoring
- [ ] Set up connection count monitoring
- [ ] Alert on high connection usage (>80%)
- [ ] Monitor long-running queries
- [ ] Check for idle connections daily
- [ ] Review logs weekly

## Summary

### Quick Recommendations

**For 16GB RAM Server:**
```conf
max_connections = 200
shared_buffers = 4GB
work_mem = 10MB
effective_cache_size = 12GB
```

**For 8GB RAM Server:**
```conf
max_connections = 150
shared_buffers = 2GB
work_mem = 8MB
effective_cache_size = 6GB
```

**For High Connection Count (>300):**
- Use PgBouncer
- Lower PostgreSQL `max_connections` to 100
- Let PgBouncer handle application connections

## Related Documentation

- [Connection Pool Fix](./DATABASE_CONNECTION_POOL_FIX.md)
- [Quick Reference](./CONNECTION_POOL_QUICK_REFERENCE.md)
- [Changes Summary](./CONNECTION_POOL_CHANGES_SUMMARY.md)
- [PostgreSQL Performance Documentation](https://www.postgresql.org/docs/current/runtime-config-connection.html)

---

_Last Updated: October 20, 2025_

