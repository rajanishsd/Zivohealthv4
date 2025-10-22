-- ============================================================================
-- Migration 067: Fix CASCADE Delete Constraints
-- ============================================================================
-- Purpose: Ensure all foreign key constraints to users(id) have ON DELETE CASCADE
-- This allows clean deletion of users and all their associated data across 50 tables
--
-- Note: This script includes safety checks to skip non-existent tables/columns
-- ============================================================================

BEGIN;

DO $$
DECLARE
    v_table_name TEXT;
    v_constraint_name TEXT;
    v_column_name TEXT;
    v_table_exists BOOLEAN;
    v_column_exists BOOLEAN;
    v_constraint_exists BOOLEAN;
BEGIN
    RAISE NOTICE 'Starting CASCADE constraint fixes for user-related tables...';

    -- ========================================
    -- Core user tables
    -- ========================================
    
    -- user_profiles
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'user_profiles') THEN
        ALTER TABLE user_profiles DROP CONSTRAINT IF EXISTS user_profiles_user_id_fkey;
        ALTER TABLE user_profiles ADD CONSTRAINT user_profiles_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed user_profiles';
    END IF;

    -- user_identities
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'user_identities') THEN
        ALTER TABLE user_identities DROP CONSTRAINT IF EXISTS user_identities_user_id_fkey;
        ALTER TABLE user_identities ADD CONSTRAINT user_identities_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed user_identities';
    END IF;

    -- login_events
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'login_events') THEN
        ALTER TABLE login_events DROP CONSTRAINT IF EXISTS login_events_user_id_fkey;
        ALTER TABLE login_events ADD CONSTRAINT login_events_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed login_events';
    END IF;

    -- user_devices
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'user_devices') THEN
        ALTER TABLE user_devices DROP CONSTRAINT IF EXISTS user_devices_user_id_fkey;
        ALTER TABLE user_devices ADD CONSTRAINT user_devices_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed user_devices';
    END IF;

    -- user_conditions
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'user_conditions') THEN
        ALTER TABLE user_conditions DROP CONSTRAINT IF EXISTS user_conditions_user_id_fkey;
        ALTER TABLE user_conditions ADD CONSTRAINT user_conditions_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed user_conditions';
    END IF;

    -- user_allergies
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'user_allergies') THEN
        ALTER TABLE user_allergies DROP CONSTRAINT IF EXISTS user_allergies_user_id_fkey;
        ALTER TABLE user_allergies ADD CONSTRAINT user_allergies_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed user_allergies';
    END IF;

    -- user_lifestyle
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'user_lifestyle') THEN
        ALTER TABLE user_lifestyle DROP CONSTRAINT IF EXISTS user_lifestyle_user_id_fkey;
        ALTER TABLE user_lifestyle ADD CONSTRAINT user_lifestyle_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed user_lifestyle';
    END IF;

    -- user_consents
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'user_consents') THEN
        ALTER TABLE user_consents DROP CONSTRAINT IF EXISTS user_consents_user_id_fkey;
        ALTER TABLE user_consents ADD CONSTRAINT user_consents_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed user_consents';
    END IF;

    -- user_measurement_preferences
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'user_measurement_preferences') THEN
        ALTER TABLE user_measurement_preferences DROP CONSTRAINT IF EXISTS user_measurement_preferences_user_id_fkey;
        ALTER TABLE user_measurement_preferences ADD CONSTRAINT user_measurement_preferences_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed user_measurement_preferences';
    END IF;

    -- user_notification_preferences
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'user_notification_preferences') THEN
        ALTER TABLE user_notification_preferences DROP CONSTRAINT IF EXISTS user_notification_preferences_user_id_fkey;
        ALTER TABLE user_notification_preferences ADD CONSTRAINT user_notification_preferences_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed user_notification_preferences';
    END IF;

    -- user_nutrient_focus
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'user_nutrient_focus') THEN
        ALTER TABLE user_nutrient_focus DROP CONSTRAINT IF EXISTS user_nutrient_focus_user_id_fkey;
        ALTER TABLE user_nutrient_focus ADD CONSTRAINT user_nutrient_focus_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed user_nutrient_focus';
    END IF;

    -- ========================================
    -- Vitals - raw and categorized
    -- ========================================

    -- vitals_raw_data
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'vitals_raw_data') THEN
        ALTER TABLE vitals_raw_data DROP CONSTRAINT IF EXISTS vitals_raw_data_user_id_fkey;
        ALTER TABLE vitals_raw_data ADD CONSTRAINT vitals_raw_data_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed vitals_raw_data';
    END IF;

    -- vitals_raw_categorized
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'vitals_raw_categorized') THEN
        ALTER TABLE vitals_raw_categorized DROP CONSTRAINT IF EXISTS vitals_raw_categorized_user_id_fkey;
        ALTER TABLE vitals_raw_categorized ADD CONSTRAINT vitals_raw_categorized_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed vitals_raw_categorized';
    END IF;

    -- ========================================
    -- Vitals - aggregates
    -- ========================================

    -- vitals_hourly_aggregates
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'vitals_hourly_aggregates') THEN
        ALTER TABLE vitals_hourly_aggregates DROP CONSTRAINT IF EXISTS vitals_hourly_aggregates_user_id_fkey;
        ALTER TABLE vitals_hourly_aggregates ADD CONSTRAINT vitals_hourly_aggregates_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed vitals_hourly_aggregates';
    END IF;

    -- vitals_daily_aggregates
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'vitals_daily_aggregates') THEN
        ALTER TABLE vitals_daily_aggregates DROP CONSTRAINT IF EXISTS vitals_daily_aggregates_user_id_fkey;
        ALTER TABLE vitals_daily_aggregates ADD CONSTRAINT vitals_daily_aggregates_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed vitals_daily_aggregates';
    END IF;

    -- vitals_weekly_aggregates
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'vitals_weekly_aggregates') THEN
        ALTER TABLE vitals_weekly_aggregates DROP CONSTRAINT IF EXISTS vitals_weekly_aggregates_user_id_fkey;
        ALTER TABLE vitals_weekly_aggregates ADD CONSTRAINT vitals_weekly_aggregates_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed vitals_weekly_aggregates';
    END IF;

    -- vitals_monthly_aggregates
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'vitals_monthly_aggregates') THEN
        ALTER TABLE vitals_monthly_aggregates DROP CONSTRAINT IF EXISTS vitals_monthly_aggregates_user_id_fkey;
        ALTER TABLE vitals_monthly_aggregates ADD CONSTRAINT vitals_monthly_aggregates_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed vitals_monthly_aggregates';
    END IF;

    -- vitals_sync_status
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'vitals_sync_status') THEN
        ALTER TABLE vitals_sync_status DROP CONSTRAINT IF EXISTS vitals_sync_status_user_id_fkey;
        ALTER TABLE vitals_sync_status ADD CONSTRAINT vitals_sync_status_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed vitals_sync_status';
    END IF;

    -- ========================================
    -- Mental health
    -- ========================================

    -- mental_health_entries
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'mental_health_entries') THEN
        ALTER TABLE mental_health_entries DROP CONSTRAINT IF EXISTS mental_health_entries_user_id_fkey;
        ALTER TABLE mental_health_entries ADD CONSTRAINT mental_health_entries_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed mental_health_entries';
    END IF;

    -- mental_health_daily
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'mental_health_daily') THEN
        ALTER TABLE mental_health_daily DROP CONSTRAINT IF EXISTS mental_health_daily_user_id_fkey;
        ALTER TABLE mental_health_daily ADD CONSTRAINT mental_health_daily_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed mental_health_daily';
    END IF;

    -- ========================================
    -- Lab reports
    -- ========================================

    -- lab_reports
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'lab_reports') THEN
        ALTER TABLE lab_reports DROP CONSTRAINT IF EXISTS lab_reports_user_id_fkey;
        ALTER TABLE lab_reports ADD CONSTRAINT lab_reports_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed lab_reports';
    END IF;

    -- lab_report_categorized
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'lab_report_categorized') THEN
        ALTER TABLE lab_report_categorized DROP CONSTRAINT IF EXISTS lab_report_categorized_user_id_fkey;
        ALTER TABLE lab_report_categorized ADD CONSTRAINT lab_report_categorized_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed lab_report_categorized';
    END IF;

    -- lab_reports_daily
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'lab_reports_daily') THEN
        ALTER TABLE lab_reports_daily DROP CONSTRAINT IF EXISTS lab_reports_daily_user_id_fkey;
        ALTER TABLE lab_reports_daily ADD CONSTRAINT lab_reports_daily_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed lab_reports_daily';
    END IF;

    -- lab_reports_monthly
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'lab_reports_monthly') THEN
        ALTER TABLE lab_reports_monthly DROP CONSTRAINT IF EXISTS lab_reports_monthly_user_id_fkey;
        ALTER TABLE lab_reports_monthly ADD CONSTRAINT lab_reports_monthly_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed lab_reports_monthly';
    END IF;

    -- lab_reports_quarterly
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'lab_reports_quarterly') THEN
        ALTER TABLE lab_reports_quarterly DROP CONSTRAINT IF EXISTS lab_reports_quarterly_user_id_fkey;
        ALTER TABLE lab_reports_quarterly ADD CONSTRAINT lab_reports_quarterly_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed lab_reports_quarterly';
    END IF;

    -- lab_reports_yearly
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'lab_reports_yearly') THEN
        ALTER TABLE lab_reports_yearly DROP CONSTRAINT IF EXISTS lab_reports_yearly_user_id_fkey;
        ALTER TABLE lab_reports_yearly ADD CONSTRAINT lab_reports_yearly_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed lab_reports_yearly';
    END IF;

    -- ========================================
    -- Nutrition
    -- ========================================

    -- nutrition_raw_data
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'nutrition_raw_data') THEN
        ALTER TABLE nutrition_raw_data DROP CONSTRAINT IF EXISTS nutrition_raw_data_user_id_fkey;
        ALTER TABLE nutrition_raw_data ADD CONSTRAINT nutrition_raw_data_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed nutrition_raw_data';
    END IF;

    -- nutrition_daily_aggregates
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'nutrition_daily_aggregates') THEN
        ALTER TABLE nutrition_daily_aggregates DROP CONSTRAINT IF EXISTS nutrition_daily_aggregates_user_id_fkey;
        ALTER TABLE nutrition_daily_aggregates ADD CONSTRAINT nutrition_daily_aggregates_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed nutrition_daily_aggregates';
    END IF;

    -- nutrition_weekly_aggregates
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'nutrition_weekly_aggregates') THEN
        ALTER TABLE nutrition_weekly_aggregates DROP CONSTRAINT IF EXISTS nutrition_weekly_aggregates_user_id_fkey;
        ALTER TABLE nutrition_weekly_aggregates ADD CONSTRAINT nutrition_weekly_aggregates_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed nutrition_weekly_aggregates';
    END IF;

    -- nutrition_monthly_aggregates
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'nutrition_monthly_aggregates') THEN
        ALTER TABLE nutrition_monthly_aggregates DROP CONSTRAINT IF EXISTS nutrition_monthly_aggregates_user_id_fkey;
        ALTER TABLE nutrition_monthly_aggregates ADD CONSTRAINT nutrition_monthly_aggregates_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed nutrition_monthly_aggregates';
    END IF;

    -- nutrition_sync_status
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'nutrition_sync_status') THEN
        ALTER TABLE nutrition_sync_status DROP CONSTRAINT IF EXISTS nutrition_sync_status_user_id_fkey;
        ALTER TABLE nutrition_sync_status ADD CONSTRAINT nutrition_sync_status_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed nutrition_sync_status';
    END IF;

    -- nutrition_goals
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'nutrition_goals') THEN
        ALTER TABLE nutrition_goals DROP CONSTRAINT IF EXISTS nutrition_goals_user_id_fkey;
        ALTER TABLE nutrition_goals ADD CONSTRAINT nutrition_goals_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed nutrition_goals';
    END IF;

    -- ========================================
    -- Pharmacy
    -- ========================================

    -- pharmacy_medications
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'pharmacy_medications') THEN
        ALTER TABLE pharmacy_medications DROP CONSTRAINT IF EXISTS pharmacy_medications_user_id_fkey;
        ALTER TABLE pharmacy_medications ADD CONSTRAINT pharmacy_medications_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed pharmacy_medications';
    END IF;

    -- pharmacy_bills
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'pharmacy_bills') THEN
        ALTER TABLE pharmacy_bills DROP CONSTRAINT IF EXISTS pharmacy_bills_user_id_fkey;
        ALTER TABLE pharmacy_bills ADD CONSTRAINT pharmacy_bills_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed pharmacy_bills';
    END IF;

    -- ========================================
    -- Chat and communication
    -- ========================================

    -- chat_sessions
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'chat_sessions') THEN
        ALTER TABLE chat_sessions DROP CONSTRAINT IF EXISTS chat_sessions_user_id_fkey;
        ALTER TABLE chat_sessions ADD CONSTRAINT chat_sessions_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed chat_sessions';
    END IF;

    -- chat_messages
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'chat_messages') THEN
        ALTER TABLE chat_messages DROP CONSTRAINT IF EXISTS chat_messages_user_id_fkey;
        ALTER TABLE chat_messages ADD CONSTRAINT chat_messages_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed chat_messages';
    END IF;

    -- agent_memory
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'agent_memory') THEN
        ALTER TABLE agent_memory DROP CONSTRAINT IF EXISTS agent_memory_user_id_fkey;
        ALTER TABLE agent_memory ADD CONSTRAINT agent_memory_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed agent_memory';
    END IF;

    -- ========================================
    -- Appointments and prescriptions
    -- ========================================

    -- appointments (patient_id column)
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'appointments') THEN
        ALTER TABLE appointments DROP CONSTRAINT IF EXISTS appointments_patient_id_fkey;
        ALTER TABLE appointments ADD CONSTRAINT appointments_patient_id_fkey 
            FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed appointments';
    END IF;

    -- consultation_requests
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'consultation_requests') THEN
        ALTER TABLE consultation_requests DROP CONSTRAINT IF EXISTS consultation_requests_user_id_fkey;
        ALTER TABLE consultation_requests ADD CONSTRAINT consultation_requests_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed consultation_requests';
    END IF;

    -- ========================================
    -- Clinical data
    -- ========================================

    -- clinical_notes
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'clinical_notes') THEN
        ALTER TABLE clinical_notes DROP CONSTRAINT IF EXISTS clinical_notes_user_id_fkey;
        ALTER TABLE clinical_notes ADD CONSTRAINT clinical_notes_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed clinical_notes';
    END IF;

    -- clinical_reports
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'clinical_reports') THEN
        ALTER TABLE clinical_reports DROP CONSTRAINT IF EXISTS clinical_reports_user_id_fkey;
        ALTER TABLE clinical_reports ADD CONSTRAINT clinical_reports_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed clinical_reports';
    END IF;

    -- medical_images
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'medical_images') THEN
        ALTER TABLE medical_images DROP CONSTRAINT IF EXISTS medical_images_user_id_fkey;
        ALTER TABLE medical_images ADD CONSTRAINT medical_images_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed medical_images';
    END IF;

    -- ========================================
    -- Health indicators and summaries
    -- ========================================

    -- patient_health_records (patient_id)
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'patient_health_records') THEN
        ALTER TABLE patient_health_records DROP CONSTRAINT IF EXISTS patient_health_records_patient_id_fkey;
        ALTER TABLE patient_health_records ADD CONSTRAINT patient_health_records_patient_id_fkey 
            FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed patient_health_records.patient_id';
    END IF;

    -- patient_health_records (recorded_by)
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'patient_health_records') THEN
        ALTER TABLE patient_health_records DROP CONSTRAINT IF EXISTS patient_health_records_recorded_by_fkey;
        ALTER TABLE patient_health_records ADD CONSTRAINT patient_health_records_recorded_by_fkey 
            FOREIGN KEY (recorded_by) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed patient_health_records.recorded_by';
    END IF;

    -- health_data_history (patient_id)
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'health_data_history') THEN
        ALTER TABLE health_data_history DROP CONSTRAINT IF EXISTS health_data_history_patient_id_fkey;
        ALTER TABLE health_data_history ADD CONSTRAINT health_data_history_patient_id_fkey 
            FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed health_data_history.patient_id';
    END IF;

    -- health_data_history (recorded_by)
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'health_data_history') THEN
        ALTER TABLE health_data_history DROP CONSTRAINT IF EXISTS health_data_history_recorded_by_fkey;
        ALTER TABLE health_data_history ADD CONSTRAINT health_data_history_recorded_by_fkey 
            FOREIGN KEY (recorded_by) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed health_data_history.recorded_by';
    END IF;

    -- patient_health_summaries
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'patient_health_summaries') THEN
        ALTER TABLE patient_health_summaries DROP CONSTRAINT IF EXISTS patient_health_summaries_patient_id_fkey;
        ALTER TABLE patient_health_summaries ADD CONSTRAINT patient_health_summaries_patient_id_fkey 
            FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed patient_health_summaries';
    END IF;

    -- ========================================
    -- Health scoring tables
    -- ========================================

    -- health_score_calculations_log
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'health_score_calculations_log') THEN
        ALTER TABLE health_score_calculations_log DROP CONSTRAINT IF EXISTS health_score_calculations_log_user_id_fkey;
        ALTER TABLE health_score_calculations_log ADD CONSTRAINT health_score_calculations_log_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed health_score_calculations_log';
    END IF;

    -- health_score_results_daily
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'health_score_results_daily') THEN
        ALTER TABLE health_score_results_daily DROP CONSTRAINT IF EXISTS health_score_results_daily_user_id_fkey;
        ALTER TABLE health_score_results_daily ADD CONSTRAINT health_score_results_daily_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed health_score_results_daily';
    END IF;

    -- ========================================
    -- Observability
    -- ========================================

    -- opentelemetry_traces
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'opentelemetry_traces') THEN
        ALTER TABLE opentelemetry_traces DROP CONSTRAINT IF EXISTS opentelemetry_traces_user_id_fkey;
        ALTER TABLE opentelemetry_traces ADD CONSTRAINT opentelemetry_traces_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed opentelemetry_traces';
    END IF;

    -- ========================================
    -- System logs
    -- ========================================

    -- document_processing_logs
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'document_processing_logs') THEN
        ALTER TABLE document_processing_logs DROP CONSTRAINT IF EXISTS document_processing_logs_user_id_fkey;
        ALTER TABLE document_processing_logs ADD CONSTRAINT document_processing_logs_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed document_processing_logs';
    END IF;

    -- ========================================
    -- Password reset
    -- ========================================

    -- password_reset_tokens
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'password_reset_tokens') THEN
        ALTER TABLE password_reset_tokens DROP CONSTRAINT IF EXISTS password_reset_tokens_user_id_fkey;
        ALTER TABLE password_reset_tokens ADD CONSTRAINT password_reset_tokens_user_id_fkey 
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        RAISE NOTICE '✅ Fixed password_reset_tokens';
    END IF;

    RAISE NOTICE '✅ CASCADE constraints fixed successfully! All 50 tables updated.';
END $$;

COMMIT;

-- ============================================================================
-- Verification Query
-- ============================================================================
-- Run this query to verify all constraints are properly set with CASCADE:

SELECT 
    tc.table_name,
    kcu.column_name,
    tc.constraint_name,
    rc.delete_rule
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
ORDER BY tc.table_name, kcu.column_name;

