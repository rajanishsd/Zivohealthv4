-- ============================================================================
-- Verify CASCADE Delete Constraints on Users Table
-- ============================================================================
-- This script checks all foreign key constraints referencing users(id)
-- and verifies they have ON DELETE CASCADE properly set
-- ============================================================================

-- 1. Check all foreign keys to users table with their delete rules
-- (Using information_schema for readable output)
SELECT 
    tc.table_name,
    kcu.column_name,
    tc.constraint_name,
    rc.delete_rule,
    CASE 
        WHEN rc.delete_rule = 'CASCADE' THEN '✅'
        ELSE '❌'
    END as status
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu 
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.referential_constraints rc 
    ON tc.constraint_name = rc.constraint_name
    AND tc.table_schema = rc.constraint_schema
JOIN information_schema.constraint_column_usage ccu 
    ON rc.unique_constraint_name = ccu.constraint_name
    AND rc.unique_constraint_schema = ccu.constraint_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND ccu.table_name = 'users'
    AND tc.table_schema = 'public'
ORDER BY 
    CASE WHEN rc.delete_rule = 'CASCADE' THEN 1 ELSE 0 END,
    tc.table_name, 
    kcu.column_name;

-- ============================================================================
-- 2. Count summary
-- ============================================================================
SELECT 
    'TOTAL CONSTRAINTS' as metric,
    COUNT(*) as count
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu 
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.referential_constraints rc 
    ON tc.constraint_name = rc.constraint_name
    AND tc.table_schema = rc.constraint_schema
JOIN information_schema.constraint_column_usage ccu 
    ON rc.unique_constraint_name = ccu.constraint_name
    AND rc.unique_constraint_schema = ccu.constraint_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND ccu.table_name = 'users'
    AND tc.table_schema = 'public'
UNION ALL
SELECT 
    'WITH CASCADE' as metric,
    COUNT(*) as count
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu 
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.referential_constraints rc 
    ON tc.constraint_name = rc.constraint_name
    AND tc.table_schema = rc.constraint_schema
JOIN information_schema.constraint_column_usage ccu 
    ON rc.unique_constraint_name = ccu.constraint_name
    AND rc.unique_constraint_schema = ccu.constraint_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND ccu.table_name = 'users'
    AND tc.table_schema = 'public'
    AND rc.delete_rule = 'CASCADE'
UNION ALL
SELECT 
    'WITHOUT CASCADE (⚠️ NEED FIX)' as metric,
    COUNT(*) as count
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu 
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.referential_constraints rc 
    ON tc.constraint_name = rc.constraint_name
    AND tc.table_schema = rc.constraint_schema
JOIN information_schema.constraint_column_usage ccu 
    ON rc.unique_constraint_name = ccu.constraint_name
    AND rc.unique_constraint_schema = ccu.constraint_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND ccu.table_name = 'users'
    AND tc.table_schema = 'public'
    AND rc.delete_rule != 'CASCADE';

-- ============================================================================
-- 3. Check specific tables from migration 067
-- ============================================================================
-- Expected tables that should have CASCADE
WITH expected_tables AS (
    SELECT unnest(ARRAY[
        'user_profiles',
        'user_identities',
        'login_events',
        'user_devices',
        'user_conditions',
        'user_allergies',
        'user_lifestyle',
        'user_consents',
        'user_measurement_preferences',
        'user_notification_preferences',
        'user_nutrient_focus',
        'vitals_raw_data',
        'vitals_raw_categorized',
        'vitals_hourly_aggregates',
        'vitals_daily_aggregates',
        'vitals_weekly_aggregates',
        'vitals_monthly_aggregates',
        'vitals_sync_status',
        'mental_health_entries',
        'mental_health_daily',
        'lab_reports',
        'lab_report_categorized',
        'lab_reports_daily',
        'lab_reports_monthly',
        'lab_reports_quarterly',
        'lab_reports_yearly',
        'nutrition_raw_data',
        'nutrition_daily_aggregates',
        'nutrition_weekly_aggregates',
        'nutrition_monthly_aggregates',
        'nutrition_sync_status',
        'nutrition_goals',
        'pharmacy_medications',
        'pharmacy_bills',
        'chat_sessions',
        'chat_messages',
        'agent_memory',
        'appointments',
        'consultation_requests',
        'clinical_notes',
        'clinical_reports',
        'medical_images',
        'patient_health_records',
        'health_data_history',
        'patient_health_summaries',
        'health_score_calculations_log',
        'health_score_results_daily',
        'opentelemetry_traces',
        'document_processing_logs',
        'password_reset_tokens'
    ]) as table_name
)
SELECT 
    et.table_name,
    COALESCE(tc.constraint_name, 'MISSING') as constraint_name,
    COALESCE(rc.delete_rule, 'N/A') as delete_rule,
    CASE 
        WHEN tc.constraint_name IS NULL THEN '❓ TABLE NOT FOUND'
        WHEN rc.delete_rule = 'CASCADE' THEN '✅ CASCADE'
        ELSE '❌ NO CASCADE'
    END as status
FROM expected_tables et
LEFT JOIN information_schema.table_constraints tc
    ON et.table_name = tc.table_name
    AND tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_schema = 'public'
LEFT JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
LEFT JOIN information_schema.referential_constraints rc 
    ON tc.constraint_name = rc.constraint_name
    AND tc.table_schema = rc.constraint_schema
LEFT JOIN information_schema.constraint_column_usage ccu 
    ON rc.unique_constraint_name = ccu.constraint_name
    AND rc.unique_constraint_schema = ccu.constraint_schema
    AND ccu.table_name = 'users'
WHERE tc.constraint_name IS NULL 
   OR (tc.constraint_name IS NOT NULL AND ccu.table_name = 'users')
ORDER BY 
    CASE 
        WHEN tc.constraint_name IS NULL THEN 2
        WHEN rc.delete_rule = 'CASCADE' THEN 0
        ELSE 1
    END,
    et.table_name;

-- ============================================================================
-- 4. Specific check for health_score_results_daily
-- ============================================================================
SELECT 
    '=== HEALTH_SCORE_RESULTS_DAILY CHECK ===' as check_type,
    tc.constraint_name,
    kcu.column_name,
    rc.delete_rule,
    CASE 
        WHEN rc.delete_rule = 'CASCADE' THEN '✅ CASCADE SET'
        ELSE '❌ NOT CASCADE'
    END as status
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu 
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.referential_constraints rc 
    ON tc.constraint_name = rc.constraint_name
WHERE tc.table_name = 'health_score_results_daily'
    AND tc.constraint_type = 'FOREIGN KEY'
    AND kcu.column_name = 'user_id';

-- ============================================================================
-- 5. Using pg_constraint (Low-level check - most reliable)
-- ============================================================================
-- confdeltype: a = no action, r = restrict, c = cascade, n = set null, d = set default
SELECT 
    '=== LOW-LEVEL CONSTRAINT CHECK ===' as check_type,
    conname as constraint_name,
    conrelid::regclass as table_name,
    confdeltype,
    CASE confdeltype
        WHEN 'a' THEN '❌ NO ACTION'
        WHEN 'r' THEN '❌ RESTRICT'
        WHEN 'c' THEN '✅ CASCADE'
        WHEN 'n' THEN '⚠️ SET NULL'
        WHEN 'd' THEN '⚠️ SET DEFAULT'
    END as delete_action
FROM pg_constraint
WHERE conrelid IN (
    SELECT oid FROM pg_class 
    WHERE relname IN (
        'user_profiles', 'user_identities', 'login_events', 'user_devices',
        'user_conditions', 'user_allergies', 'user_lifestyle', 'user_consents',
        'user_measurement_preferences', 'user_notification_preferences',
        'health_score_results_daily', 'health_score_calculations_log',
        'pharmacy_medications', 'pharmacy_bills', 'vitals_raw_data'
    )
)
AND contype = 'f'  -- Foreign key constraints only
AND confrelid = 'users'::regclass  -- References users table
ORDER BY 
    CASE confdeltype 
        WHEN 'c' THEN 0 
        ELSE 1 
    END,
    conrelid::regclass::text;

-- ============================================================================
-- End of verification script
-- ============================================================================

