-- Backfill duration_minutes for sleep records
-- Converts total_value (hours) to duration_minutes (minutes)

-- Script: 02_backfill_sleep_duration.sql
-- Purpose: Populate duration_minutes field for existing sleep records where it's NULL
-- Run this AFTER adding metric anchors (01_add_metric_anchors.sql)

-- IMPORTANT: Review the dry-run query first before running the actual update!

-- ==============================================================================
-- DRY RUN: Preview what will be changed (run this first)
-- ==============================================================================

SELECT 
    user_id,
    date,
    total_value as current_hours,
    total_value * 60.0 as new_duration_minutes,
    average_value as fallback_hours,
    unit,
    CASE 
        WHEN total_value IS NOT NULL AND total_value > 0 THEN 'Use total_value'
        WHEN average_value IS NOT NULL AND average_value > 0 THEN 'Use average_value'
        ELSE 'Cannot fix - no valid value'
    END as action
FROM vitals_daily_aggregates
WHERE metric_type = 'Sleep'
  AND duration_minutes IS NULL
ORDER BY user_id, date
LIMIT 100;  -- Preview first 100 records

-- Count records by action type
SELECT 
    CASE 
        WHEN total_value IS NOT NULL AND total_value > 0 THEN 'Will fix from total_value'
        WHEN average_value IS NOT NULL AND average_value > 0 THEN 'Will fix from average_value'
        WHEN total_value = 0 AND average_value = 0 THEN 'Skip (no sleep recorded - zeros)'
        ELSE 'Cannot fix (no valid data)'
    END as status,
    COUNT(*) as record_count
FROM vitals_daily_aggregates
WHERE metric_type = 'Sleep'
  AND duration_minutes IS NULL
GROUP BY status
ORDER BY 
    CASE 
        WHEN status LIKE 'Will fix%' THEN 1
        WHEN status LIKE 'Skip%' THEN 2
        ELSE 3
    END;

-- ==============================================================================
-- ACTUAL UPDATE: Run this after reviewing dry-run results
-- ==============================================================================

-- IMPORTANT: Uncomment the BEGIN/COMMIT block below to execute

-- BEGIN;

-- Update records where total_value exists and is valid (hours -> minutes)
-- Skip records where total_value = 0 (no sleep recorded that day)
UPDATE vitals_daily_aggregates
SET 
    duration_minutes = total_value * 60.0,
    updated_at = NOW()
WHERE metric_type = 'Sleep'
  AND duration_minutes IS NULL
  AND total_value IS NOT NULL
  AND total_value > 0  -- Excludes zero values (no sleep recorded)

-- Get count of records updated from total_value
DO $$
DECLARE
    updated_count INTEGER;
BEGIN
    GET DIAGNOSTICS updated_count = ROW_COUNT;
    RAISE NOTICE '✓ Updated % records from total_value', updated_count;
END $$;

-- Update remaining records using average_value as fallback
UPDATE vitals_daily_aggregates
SET 
    duration_minutes = average_value * 60.0,
    updated_at = NOW()
WHERE metric_type = 'Sleep'
  AND duration_minutes IS NULL
  AND average_value IS NOT NULL
  AND average_value > 0;

-- Get count of records updated from average_value
DO $$
DECLARE
    updated_count INTEGER;
BEGIN
    GET DIAGNOSTICS updated_count = ROW_COUNT;
    RAISE NOTICE '✓ Updated % records from average_value (fallback)', updated_count;
END $$;

-- COMMIT;

-- ==============================================================================
-- VERIFICATION: Run this after update to verify results
-- ==============================================================================

-- Check records that were updated
SELECT 
    COUNT(*) as total_sleep_records,
    COUNT(duration_minutes) as with_duration_minutes,
    COUNT(*) - COUNT(duration_minutes) as still_missing,
    ROUND(AVG(duration_minutes), 2) as avg_duration_minutes,
    ROUND(MIN(duration_minutes), 2) as min_duration_minutes,
    ROUND(MAX(duration_minutes), 2) as max_duration_minutes
FROM vitals_daily_aggregates
WHERE metric_type = 'Sleep';

-- Show sample of recently updated records
SELECT 
    user_id,
    date,
    total_value as hours,
    duration_minutes as minutes,
    duration_minutes / 60.0 as calculated_hours,
    unit,
    updated_at
FROM vitals_daily_aggregates
WHERE metric_type = 'Sleep'
  AND duration_minutes IS NOT NULL
ORDER BY updated_at DESC
LIMIT 20;

-- Check for any remaining NULL duration_minutes
-- NOTE: Records with total_value=0 and average_value=0 are expected to remain NULL
--       These represent days where no sleep was recorded
SELECT 
    user_id,
    date,
    total_value,
    average_value,
    duration_minutes,
    unit,
    CASE 
        WHEN total_value = 0 AND average_value = 0 THEN 'No sleep recorded (OK)'
        ELSE 'Data quality issue'
    END as reason
FROM vitals_daily_aggregates
WHERE metric_type = 'Sleep'
  AND duration_minutes IS NULL
LIMIT 10;

-- ==============================================================================
-- OPTIONAL CLEANUP: Remove invalid sleep records (zero values)
-- ==============================================================================

-- These are sleep records where no sleep was actually recorded (total_value=0, average_value=0)
-- They won't affect health score calculation, but you may want to clean them up

-- Preview records that would be deleted
-- SELECT user_id, date, total_value, average_value
-- FROM vitals_daily_aggregates
-- WHERE metric_type = 'Sleep'
--   AND total_value = 0
--   AND average_value = 0
--   AND duration_minutes IS NULL;

-- Uncomment to delete these records:
-- BEGIN;
-- DELETE FROM vitals_daily_aggregates
-- WHERE metric_type = 'Sleep'
--   AND total_value = 0
--   AND average_value = 0
--   AND duration_minutes IS NULL;
-- COMMIT;

-- ==============================================================================
-- ROLLBACK (if needed): Uncomment to revert changes
-- ==============================================================================

-- WARNING: Only run this if you need to undo the changes!
-- 
-- UPDATE vitals_daily_aggregates
-- SET 
--     duration_minutes = NULL,
--     updated_at = NOW()
-- WHERE metric_type = 'Sleep'
--   AND updated_at > '2025-10-23 12:00:00'  -- Replace with timestamp when update was run
--   AND duration_minutes IS NOT NULL;

-- ==============================================================================
-- SUMMARY QUERY: Overall health score readiness
-- ==============================================================================

-- Check if health score calculation is ready
SELECT 
    'Metric Anchors' as component,
    COUNT(*) as count,
    CASE WHEN COUNT(*) >= 15 THEN '✓ Ready' ELSE '✗ Missing' END as status
FROM metric_anchor_registry
WHERE active = true

UNION ALL

SELECT 
    'Sleep Records with duration_minutes' as component,
    COUNT(*) as count,
    CASE WHEN COUNT(*) > 0 THEN '✓ Ready' ELSE '✗ Missing' END as status
FROM vitals_daily_aggregates
WHERE metric_type = 'Sleep'
  AND duration_minutes IS NOT NULL

UNION ALL

SELECT 
    'Recent Health Scores' as component,
    COUNT(*) as count,
    CASE WHEN COUNT(*) > 0 THEN '✓ Ready' ELSE '⚠ Not computed yet' END as status
FROM health_score_results_daily
WHERE date >= CURRENT_DATE - INTERVAL '7 days';

