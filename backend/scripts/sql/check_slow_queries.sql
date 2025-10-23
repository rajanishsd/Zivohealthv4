-- Diagnostic script to identify slow queries
-- Run this to see what's causing the slow query warnings

-- ==============================================================================
-- 1. Check current slow queries
-- ==============================================================================

-- Show currently running queries
SELECT 
    pid,
    now() - query_start as duration,
    usename,
    datname,
    state,
    LEFT(query, 100) as query_preview
FROM pg_stat_activity
WHERE state != 'idle'
  AND query NOT LIKE '%pg_stat_activity%'
ORDER BY duration DESC;

-- ==============================================================================
-- 2. Check query statistics (requires pg_stat_statements extension)
-- ==============================================================================

-- Top 10 slowest queries by average time
SELECT 
    calls,
    ROUND(mean_exec_time::numeric, 2) as avg_time_ms,
    ROUND(total_exec_time::numeric, 2) as total_time_ms,
    LEFT(query, 150) as query_preview
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat_statements%'
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Top 10 queries by total time
SELECT 
    calls,
    ROUND(mean_exec_time::numeric, 2) as avg_time_ms,
    ROUND(total_exec_time::numeric, 2) as total_time_ms,
    LEFT(query, 150) as query_preview
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat_statements%'
ORDER BY total_exec_time DESC
LIMIT 10;

-- ==============================================================================
-- 3. Check missing indexes
-- ==============================================================================

-- Tables that would benefit from indexes
SELECT 
    schemaname,
    tablename,
    seq_scan,
    seq_tup_read,
    idx_scan,
    seq_tup_read / seq_scan as avg_seq_tup_read
FROM pg_stat_user_tables
WHERE seq_scan > 0
ORDER BY seq_tup_read DESC
LIMIT 10;

-- ==============================================================================
-- 4. Check table sizes and bloat
-- ==============================================================================

SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as index_size
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN ('vitals_daily_aggregates', 'health_score_results_daily', 'lab_report_categorized', 'vitals_raw_data')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- ==============================================================================
-- 5. Check existing indexes on key tables
-- ==============================================================================

SELECT 
    t.tablename,
    i.indexname,
    pg_size_pretty(pg_relation_size(i.indexname::regclass)) as index_size,
    idx_scan as times_used,
    idx_tup_read as tuples_read
FROM pg_tables t
LEFT JOIN pg_indexes ix ON t.tablename = ix.tablename
LEFT JOIN pg_stat_user_indexes i ON ix.indexname = i.indexname
WHERE t.schemaname = 'public'
  AND t.tablename IN ('vitals_daily_aggregates', 'health_score_results_daily')
ORDER BY t.tablename, idx_scan DESC;

-- ==============================================================================
-- 6. Test query performance
-- ==============================================================================

-- Test vitals dashboard query
EXPLAIN ANALYZE
SELECT 
    metric_type,
    date,
    total_value,
    average_value,
    duration_minutes
FROM vitals_daily_aggregates
WHERE user_id = 1
  AND date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY date DESC;

-- Test health score query
EXPLAIN ANALYZE
SELECT *
FROM health_score_results_daily
WHERE user_id = 1
  AND date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY date DESC;

-- Test sleep query
EXPLAIN ANALYZE
SELECT *
FROM vitals_daily_aggregates
WHERE user_id = 1
  AND metric_type = 'Sleep'
  AND date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY date DESC;

