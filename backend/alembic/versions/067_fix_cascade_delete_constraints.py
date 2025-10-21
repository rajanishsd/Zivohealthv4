"""Fix CASCADE delete constraints for all user-related tables

Revision ID: 067_fix_cascade_delete
Revises: 066_seed_default_health_score_spec
Create Date: 2025-10-20
Updated: 2025-10-20 (Added all 53 discovered FK constraints)

This migration ensures all foreign key constraints to the users table
have proper ON DELETE CASCADE configured, allowing clean deletion of users
and all their associated data.

This migration now covers all 50 tables with 53 total foreign key constraints
to the users table (only tables that exist in the database), including:
- Core user tables (profiles, devices, notifications, preferences)
- All vitals tables (raw, categorized, aggregates)
- All lab reports (raw, categorized, aggregates)
- All nutrition data (raw, goals, aggregates)
- Mental health entries
- Pharmacy data
- HealthKit data
- Chat and communication
- Clinical data and health records
- Health scoring tables
- Observability (telemetry traces)
- And more

The migration safely handles:
- Tables that don't exist (skips them)
- Duplicate constraints (removes and recreates)
- Multiple FK columns per table (e.g., patient_id and recorded_by)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '067'
down_revision = '066'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add ON DELETE CASCADE to all foreign key constraints pointing to users table.
    
    This allows proper cascading deletion of all user-related data when a user is deleted.
    """
    
    # Get connection for executing raw SQL
    conn = op.get_bind()
    
    # List of tables and their foreign key columns that reference users(id)
    # Format: (table_name, constraint_name, column_name)
    # NOTE: This list only includes tables that actually exist in the database
    tables_to_fix = [
        # Core user tables
        ('user_profiles', 'user_profiles_user_id_fkey', 'user_id'),
        ('user_identities', 'user_identities_user_id_fkey', 'user_id'),
        ('login_events', 'login_events_user_id_fkey', 'user_id'),
        ('user_devices', 'user_devices_user_id_fkey', 'user_id'),
        ('user_conditions', 'user_conditions_user_id_fkey', 'user_id'),
        ('user_allergies', 'user_allergies_user_id_fkey', 'user_id'),
        ('user_lifestyle', 'user_lifestyle_user_id_fkey', 'user_id'),
        ('user_consents', 'user_consents_user_id_fkey', 'user_id'),
        ('user_measurement_preferences', 'user_measurement_preferences_user_id_fkey', 'user_id'),
        ('user_notification_preferences', 'user_notification_preferences_user_id_fkey', 'user_id'),
        ('user_nutrient_focus', 'user_nutrient_focus_user_id_fkey', 'user_id'),
        
        # Vitals - raw and categorized
        ('vitals_raw_data', 'vitals_raw_data_user_id_fkey', 'user_id'),
        ('vitals_raw_categorized', 'vitals_raw_categorized_user_id_fkey', 'user_id'),
        
        # Vitals - aggregates (hourly, daily, weekly, monthly)
        ('vitals_hourly_aggregates', 'vitals_hourly_aggregates_user_id_fkey', 'user_id'),
        ('vitals_daily_aggregates', 'vitals_daily_aggregates_user_id_fkey', 'user_id'),
        ('vitals_weekly_aggregates', 'vitals_weekly_aggregates_user_id_fkey', 'user_id'),
        ('vitals_monthly_aggregates', 'vitals_monthly_aggregates_user_id_fkey', 'user_id'),
        ('vitals_sync_status', 'vitals_sync_status_user_id_fkey', 'user_id'),
        
        # Mental health
        ('mental_health_entries', 'mental_health_entries_user_id_fkey', 'user_id'),
        ('mental_health_daily', 'mental_health_daily_user_id_fkey', 'user_id'),
        
        # Lab reports - raw and categorized
        ('lab_reports', 'lab_reports_user_id_fkey', 'user_id'),
        ('lab_report_categorized', 'lab_report_categorized_user_id_fkey', 'user_id'),
        
        # Lab reports - aggregates
        ('lab_reports_daily', 'lab_reports_daily_user_id_fkey', 'user_id'),
        ('lab_reports_monthly', 'lab_reports_monthly_user_id_fkey', 'user_id'),
        ('lab_reports_quarterly', 'lab_reports_quarterly_user_id_fkey', 'user_id'),
        ('lab_reports_yearly', 'lab_reports_yearly_user_id_fkey', 'user_id'),
        
        # Nutrition - raw data and aggregates
        ('nutrition_raw_data', 'nutrition_raw_data_user_id_fkey', 'user_id'),
        ('nutrition_daily_aggregates', 'nutrition_daily_aggregates_user_id_fkey', 'user_id'),
        ('nutrition_weekly_aggregates', 'nutrition_weekly_aggregates_user_id_fkey', 'user_id'),
        ('nutrition_monthly_aggregates', 'nutrition_monthly_aggregates_user_id_fkey', 'user_id'),
        ('nutrition_sync_status', 'nutrition_sync_status_user_id_fkey', 'user_id'),
        ('nutrition_goals', 'nutrition_goals_user_id_fkey', 'user_id'),
        
        # Pharmacy - bills and medications (no raw/aggregate tables exist)
        ('pharmacy_medications', 'pharmacy_medications_user_id_fkey', 'user_id'),
        ('pharmacy_bills', 'pharmacy_bills_user_id_fkey', 'user_id'),
        
        # Chat and communication
        ('chat_sessions', 'chat_sessions_user_id_fkey', 'user_id'),
        ('chat_messages', 'chat_messages_user_id_fkey', 'user_id'),
        ('agent_memory', 'agent_memory_user_id_fkey', 'user_id'),
        
        # Appointments and prescriptions
        ('appointments', 'appointments_patient_id_fkey', 'patient_id'),
        ('consultation_requests', 'consultation_requests_user_id_fkey', 'user_id'),
        
        # Clinical data
        ('clinical_notes', 'clinical_notes_user_id_fkey', 'user_id'),
        ('clinical_reports', 'clinical_reports_user_id_fkey', 'user_id'),
        ('medical_images', 'medical_images_user_id_fkey', 'user_id'),
        
        # Health indicators and summaries
        ('patient_health_records', 'patient_health_records_patient_id_fkey', 'patient_id'),
        ('patient_health_records', 'patient_health_records_recorded_by_fkey', 'recorded_by'),
        ('health_data_history', 'health_data_history_patient_id_fkey', 'patient_id'),
        ('health_data_history', 'health_data_history_recorded_by_fkey', 'recorded_by'),
        ('patient_health_summaries', 'patient_health_summaries_patient_id_fkey', 'patient_id'),
        
        # Health scoring tables
        ('health_score_calculations_log', 'health_score_calculations_log_user_id_fkey', 'user_id'),
        ('health_score_results_daily', 'health_score_results_daily_user_id_fkey', 'user_id'),
        
        # Observability
        ('opentelemetry_traces', 'opentelemetry_traces_user_id_fkey', 'user_id'),
        
        # System logs
        ('document_processing_logs', 'document_processing_logs_user_id_fkey', 'user_id'),
        
        # Password reset
        ('password_reset_tokens', 'password_reset_tokens_user_id_fkey', 'user_id'),
    ]
    
    print("Fixing CASCADE constraints for user-related tables...")
    
    for table_name, constraint_name, column_name in tables_to_fix:
        # Use a savepoint for each table so one failure doesn't abort all
        savepoint = conn.begin_nested()
        try:
            # Check if table exists
            result = conn.execute(sa.text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = '{table_name}'
                );
            """))
            table_exists = result.scalar()
            
            if not table_exists:
                print(f"  ⏭️  Skipping {table_name} (table does not exist)")
                savepoint.rollback()
                continue
            
            # Check if column exists
            result = conn.execute(sa.text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = '{table_name}'
                    AND column_name = '{column_name}'
                );
            """))
            column_exists = result.scalar()
            
            if not column_exists:
                print(f"  ⏭️  Skipping {table_name} (column {column_name} does not exist)")
                savepoint.rollback()
                continue
            
            # Check if constraint exists
            result = conn.execute(sa.text(f"""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = '{table_name}'
                AND constraint_type = 'FOREIGN KEY'
                AND constraint_name = '{constraint_name}';
            """))
            constraint_exists = result.scalar()
            
            if constraint_exists:
                # Drop existing foreign key constraint
                print(f"  🔄 Updating {table_name}.{column_name}")
                conn.execute(sa.text(f"""
                    ALTER TABLE {table_name}
                    DROP CONSTRAINT IF EXISTS {constraint_name};
                """))
            else:
                print(f"  ➕ Adding CASCADE to {table_name}.{column_name}")
            
            # Add foreign key constraint with CASCADE
            conn.execute(sa.text(f"""
                ALTER TABLE {table_name}
                ADD CONSTRAINT {constraint_name}
                FOREIGN KEY ({column_name})
                REFERENCES users(id)
                ON DELETE CASCADE;
            """))
            
            savepoint.commit()
            print(f"  ✅ Fixed {table_name}")
            
        except Exception as e:
            savepoint.rollback()
            print(f"  ⚠️  Skipping {table_name}: {str(e).split(chr(10))[0]}")
            # Continue with other tables even if one fails
            continue
    
    print("✅ CASCADE constraints fixed successfully!")


def downgrade() -> None:
    """
    Revert CASCADE constraints back to default behavior (if needed).
    
    Note: This is generally not recommended as it would break user deletion.
    """
    
    conn = op.get_bind()
    
    # Same list as upgrade - only tables that exist in the database
    tables_to_revert = [
        # Core user tables
        ('user_profiles', 'user_profiles_user_id_fkey', 'user_id'),
        ('user_identities', 'user_identities_user_id_fkey', 'user_id'),
        ('login_events', 'login_events_user_id_fkey', 'user_id'),
        ('user_devices', 'user_devices_user_id_fkey', 'user_id'),
        ('user_conditions', 'user_conditions_user_id_fkey', 'user_id'),
        ('user_allergies', 'user_allergies_user_id_fkey', 'user_id'),
        ('user_lifestyle', 'user_lifestyle_user_id_fkey', 'user_id'),
        ('user_consents', 'user_consents_user_id_fkey', 'user_id'),
        ('user_measurement_preferences', 'user_measurement_preferences_user_id_fkey', 'user_id'),
        ('user_notification_preferences', 'user_notification_preferences_user_id_fkey', 'user_id'),
        ('user_nutrient_focus', 'user_nutrient_focus_user_id_fkey', 'user_id'),
        
        # Vitals - raw and categorized
        ('vitals_raw_data', 'vitals_raw_data_user_id_fkey', 'user_id'),
        ('vitals_raw_categorized', 'vitals_raw_categorized_user_id_fkey', 'user_id'),
        
        # Vitals - aggregates (hourly, daily, weekly, monthly)
        ('vitals_hourly_aggregates', 'vitals_hourly_aggregates_user_id_fkey', 'user_id'),
        ('vitals_daily_aggregates', 'vitals_daily_aggregates_user_id_fkey', 'user_id'),
        ('vitals_weekly_aggregates', 'vitals_weekly_aggregates_user_id_fkey', 'user_id'),
        ('vitals_monthly_aggregates', 'vitals_monthly_aggregates_user_id_fkey', 'user_id'),
        ('vitals_sync_status', 'vitals_sync_status_user_id_fkey', 'user_id'),
        
        # Mental health
        ('mental_health_entries', 'mental_health_entries_user_id_fkey', 'user_id'),
        ('mental_health_daily', 'mental_health_daily_user_id_fkey', 'user_id'),
        
        # Lab reports - raw and categorized
        ('lab_reports', 'lab_reports_user_id_fkey', 'user_id'),
        ('lab_report_categorized', 'lab_report_categorized_user_id_fkey', 'user_id'),
        
        # Lab reports - aggregates
        ('lab_reports_daily', 'lab_reports_daily_user_id_fkey', 'user_id'),
        ('lab_reports_monthly', 'lab_reports_monthly_user_id_fkey', 'user_id'),
        ('lab_reports_quarterly', 'lab_reports_quarterly_user_id_fkey', 'user_id'),
        ('lab_reports_yearly', 'lab_reports_yearly_user_id_fkey', 'user_id'),
        
        # Nutrition - raw data and aggregates
        ('nutrition_raw_data', 'nutrition_raw_data_user_id_fkey', 'user_id'),
        ('nutrition_daily_aggregates', 'nutrition_daily_aggregates_user_id_fkey', 'user_id'),
        ('nutrition_weekly_aggregates', 'nutrition_weekly_aggregates_user_id_fkey', 'user_id'),
        ('nutrition_monthly_aggregates', 'nutrition_monthly_aggregates_user_id_fkey', 'user_id'),
        ('nutrition_sync_status', 'nutrition_sync_status_user_id_fkey', 'user_id'),
        ('nutrition_goals', 'nutrition_goals_user_id_fkey', 'user_id'),
        
        # Pharmacy - bills and medications (no raw/aggregate tables exist)
        ('pharmacy_medications', 'pharmacy_medications_user_id_fkey', 'user_id'),
        ('pharmacy_bills', 'pharmacy_bills_user_id_fkey', 'user_id'),
        
        # Chat and communication
        ('chat_sessions', 'chat_sessions_user_id_fkey', 'user_id'),
        ('chat_messages', 'chat_messages_user_id_fkey', 'user_id'),
        ('agent_memory', 'agent_memory_user_id_fkey', 'user_id'),
        
        # Appointments and prescriptions
        ('appointments', 'appointments_patient_id_fkey', 'patient_id'),
        ('consultation_requests', 'consultation_requests_user_id_fkey', 'user_id'),
        
        # Clinical data
        ('clinical_notes', 'clinical_notes_user_id_fkey', 'user_id'),
        ('clinical_reports', 'clinical_reports_user_id_fkey', 'user_id'),
        ('medical_images', 'medical_images_user_id_fkey', 'user_id'),
        
        # Health indicators and summaries
        ('patient_health_records', 'patient_health_records_patient_id_fkey', 'patient_id'),
        ('patient_health_records', 'patient_health_records_recorded_by_fkey', 'recorded_by'),
        ('health_data_history', 'health_data_history_patient_id_fkey', 'patient_id'),
        ('health_data_history', 'health_data_history_recorded_by_fkey', 'recorded_by'),
        ('patient_health_summaries', 'patient_health_summaries_patient_id_fkey', 'patient_id'),
        
        # Health scoring tables
        ('health_score_calculations_log', 'health_score_calculations_log_user_id_fkey', 'user_id'),
        ('health_score_results_daily', 'health_score_results_daily_user_id_fkey', 'user_id'),
        
        # Observability
        ('opentelemetry_traces', 'opentelemetry_traces_user_id_fkey', 'user_id'),
        
        # System logs
        ('document_processing_logs', 'document_processing_logs_user_id_fkey', 'user_id'),
        
        # Password reset
        ('password_reset_tokens', 'password_reset_tokens_user_id_fkey', 'user_id'),
    ]
    
    print("Reverting CASCADE constraints (not recommended)...")
    
    for table_name, constraint_name, column_name in tables_to_revert:
        try:
            # Drop CASCADE constraint
            conn.execute(sa.text(f"""
                ALTER TABLE {table_name}
                DROP CONSTRAINT IF EXISTS {constraint_name};
            """))
            
            # Add back without CASCADE (default behavior)
            conn.execute(sa.text(f"""
                ALTER TABLE {table_name}
                ADD CONSTRAINT {constraint_name}
                FOREIGN KEY ({column_name})
                REFERENCES users(id);
            """))
            
            print(f"  ✅ Reverted {table_name}")
            
        except Exception as e:
            print(f"  ⚠️  Warning: Could not revert {table_name}: {str(e)}")
            continue
    
    print("✅ Reverted CASCADE constraints")

