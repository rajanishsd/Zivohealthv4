-- Recalculate health scores after updating metrics
-- This script will mark scores for recalculation by deleting old scores
-- The health score calculation will happen automatically via:
-- 1. API calls when users access their health data
-- 2. Background jobs (if configured)
-- 3. Manual trigger via Python script

-- Script: 03_recalculate_health_scores.sql
-- Purpose: Clear old health scores to trigger recalculation with new metrics
-- Run this AFTER adding metric anchors and backfilling sleep data

-- ==============================================================================
-- PREVIEW: Check existing health scores
-- ==============================================================================

-- Count scores by date range
SELECT 
    DATE_TRUNC('week', date) as week,
    COUNT(*) as score_count,
    ROUND(AVG(overall_score), 2) as avg_overall_score,
    COUNT(DISTINCT user_id) as unique_users
FROM health_score_results_daily
GROUP BY week
ORDER BY week DESC
LIMIT 10;

-- Check scores for specific date range
SELECT 
    date,
    COUNT(*) as users_scored,
    ROUND(AVG(overall_score), 2) as avg_score,
    ROUND(MIN(overall_score), 2) as min_score,
    ROUND(MAX(overall_score), 2) as max_score,
    ROUND(AVG(confidence), 2) as avg_confidence
FROM health_score_results_daily
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY date
ORDER BY date DESC;

-- ==============================================================================
-- OPTION 1: Delete all scores for full recalculation (RECOMMENDED)
-- ==============================================================================

-- This will force all scores to be recalculated with the new metrics
-- Uncomment to execute:

-- BEGIN;
-- 
-- -- Backup count
-- SELECT COUNT(*) as scores_to_delete FROM health_score_results_daily;
-- 
-- -- Delete all health scores
-- DELETE FROM health_score_results_daily;
-- 
-- -- Delete calculation logs too
-- DELETE FROM health_score_calculations_log;
-- 
-- COMMIT;

-- ==============================================================================
-- OPTION 2: Delete scores for last N days only (SAFER)
-- ==============================================================================

-- Only recalculate recent scores (e.g., last 30 days)
-- Uncomment to execute:

-- BEGIN;
-- 
-- -- Preview what will be deleted
-- SELECT 
--     COUNT(*) as scores_to_delete,
--     MIN(date) as oldest_date,
--     MAX(date) as newest_date
-- FROM health_score_results_daily
-- WHERE date >= CURRENT_DATE - INTERVAL '30 days';
-- 
-- -- Delete scores for last 30 days
-- DELETE FROM health_score_results_daily
-- WHERE date >= CURRENT_DATE - INTERVAL '30 days';
-- 
-- -- Delete corresponding logs
-- DELETE FROM health_score_calculations_log
-- WHERE DATE(calculated_at) >= CURRENT_DATE - INTERVAL '30 days';
-- 
-- COMMIT;

-- ==============================================================================
-- OPTION 3: Delete scores for specific user(s)
-- ==============================================================================

-- Recalculate for specific users only
-- Uncomment to execute:

-- BEGIN;
-- 
-- -- For a single user
-- DELETE FROM health_score_results_daily
-- WHERE user_id = 1;
-- 
-- DELETE FROM health_score_calculations_log
-- WHERE user_id = 1;
-- 
-- -- For multiple users
-- -- DELETE FROM health_score_results_daily
-- -- WHERE user_id IN (1, 2, 3);
-- 
-- COMMIT;

-- ==============================================================================
-- OPTION 4: Delete only zero scores (those that were broken)
-- ==============================================================================

-- Only delete scores that were calculated as zero (likely broken)
-- Uncomment to execute:

-- BEGIN;
-- 
-- -- Preview zero scores
-- SELECT 
--     user_id,
--     COUNT(*) as zero_score_days,
--     MIN(date) as first_zero,
--     MAX(date) as last_zero
-- FROM health_score_results_daily
-- WHERE overall_score = 0
-- GROUP BY user_id;
-- 
-- -- Delete zero scores
-- DELETE FROM health_score_results_daily
-- WHERE overall_score = 0;
-- 
-- COMMIT;

-- ==============================================================================
-- VERIFICATION: Check deletion results
-- ==============================================================================

-- Confirm scores were deleted
SELECT 
    COUNT(*) as remaining_scores,
    MIN(date) as oldest_score_date,
    MAX(date) as newest_score_date,
    COUNT(DISTINCT user_id) as users_with_scores
FROM health_score_results_daily;

-- Check which users need recalculation
SELECT 
    u.id as user_id,
    u.email,
    COUNT(hs.id) as scores_count,
    MAX(hs.date) as last_score_date,
    CASE 
        WHEN MAX(hs.date) IS NULL THEN 'Needs calculation'
        WHEN MAX(hs.date) < CURRENT_DATE - INTERVAL '7 days' THEN 'Outdated - needs recalc'
        ELSE 'Recent scores exist'
    END as status
FROM users u
LEFT JOIN health_score_results_daily hs ON u.id = hs.user_id
WHERE u.id IN (SELECT DISTINCT user_id FROM vitals_daily_aggregates LIMIT 10)  -- Users with vitals data
GROUP BY u.id, u.email
ORDER BY u.id;

-- ==============================================================================
-- NOTES
-- ==============================================================================

-- After deleting scores, you need to trigger recalculation:
-- 
-- Method 1: Via API (recommended for production)
--   Use the Python script: recalculate_health_scores.py
-- 
-- Method 2: Via application code
--   Health scores are calculated on-demand when users access their health data
-- 
-- Method 3: Via background job
--   If you have a scheduled job, it will recalculate automatically

