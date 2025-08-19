"""Fix vitals enum values to match schema

Revision ID: 006_fix_vitals_enum_values
Revises: 005_add_unified_vitals_system
Create Date: 2025-06-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006_fix_vitals_enum_values'
down_revision = '005_add_unified_vitals_system'
branch_labels = None
depends_on = None

def upgrade():
    # Drop the old enum type (this will cascade to tables)
    op.execute('DROP TYPE IF EXISTS vitalmetrictype CASCADE')
    op.execute('DROP TYPE IF EXISTS vitaldatasource CASCADE')
    
    # Create new enum types with correct values
    vital_metric_type = postgresql.ENUM(
        'Heart Rate', 'Blood Pressure Systolic', 'Blood Pressure Diastolic',
        'Blood Sugar', 'Temperature', 'Weight', 'Height', 'BMI', 'Steps',
        'Active Energy', 'Resting Energy', 'Exercise Time', 'Stand Hours',
        'Sleep', 'Respiratory Rate', 'Oxygen Saturation', 'Workouts',
        'Distance Walking', 'Flights Climbed', 'Apple Exercise Time',
        'Apple Stand Time', 'Environmental Audio Exposure', 'Headphone Audio Exposure',
        'Walking Double Support Percentage', 'Six Minute Walk Test Distance',
        'Walking Speed', 'Walking Step Length', 'Walking Asymmetry Percentage',
        'Stair Ascent Speed', 'Stair Descent Speed', 'Oxygen Saturation',
        name='vitalmetrictype'
    )
    vital_metric_type.create(op.get_bind())
    
    vital_data_source = postgresql.ENUM(
        'apple_healthkit', 'manual_entry', 'document_extraction', 'device_sync', 'api_import',
        name='vitaldatasource'
    )
    vital_data_source.create(op.get_bind())
    
    # Recreate the vitals_raw_data table with correct enum
    op.create_table('vitals_raw_data_new',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('metric_type', sa.Enum('Heart Rate', 'Blood Pressure Systolic', 'Blood Pressure Diastolic', 'Blood Sugar', 'Temperature', 'Weight', 'Height', 'BMI', 'Steps', 'Active Energy', 'Resting Energy', 'Exercise Time', 'Stand Hours', 'Sleep', 'Respiratory Rate', 'Oxygen Saturation', 'Workouts', 'Distance Walking', 'Flights Climbed', 'Apple Exercise Time', 'Apple Stand Time', 'Environmental Audio Exposure', 'Headphone Audio Exposure', 'Walking Double Support Percentage', 'Six Minute Walk Test Distance', 'Walking Speed', 'Walking Step Length', 'Walking Asymmetry Percentage', 'Stair Ascent Speed', 'Stair Descent Speed', name='vitalmetrictype'), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=50), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=False),
        sa.Column('data_source', sa.Enum('apple_healthkit', 'manual_entry', 'document_extraction', 'device_sync', 'api_import', name='vitaldatasource'), nullable=False),
        sa.Column('source_device', sa.String(length=255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Copy data from old table if it exists
    op.execute("""
        INSERT INTO vitals_raw_data_new (id, user_id, metric_type, value, unit, start_date, end_date, data_source, source_device, notes, confidence_score, created_at, updated_at)
        SELECT id, user_id, 
               CASE metric_type
                   WHEN 'HEART_RATE' THEN 'Heart Rate'
                   WHEN 'BLOOD_PRESSURE_SYSTOLIC' THEN 'Blood Pressure Systolic'
                   WHEN 'BLOOD_PRESSURE_DIASTOLIC' THEN 'Blood Pressure Diastolic'
                   WHEN 'BLOOD_SUGAR' THEN 'Blood Sugar'
                   WHEN 'BODY_TEMPERATURE' THEN 'Temperature'
                   WHEN 'BODY_MASS' THEN 'Weight'
                   WHEN 'STEP_COUNT' THEN 'Steps'
                   WHEN 'STAND_TIME' THEN 'Stand Hours'
                   WHEN 'ACTIVE_ENERGY' THEN 'Active Energy'
                   WHEN 'FLIGHTS_CLIMBED' THEN 'Flights Climbed'
                   WHEN 'WORKOUTS' THEN 'Workouts'
                   WHEN 'WORKOUT_TYPE' THEN 'Workouts'
                   WHEN 'SLEEP_ANALYSIS' THEN 'Sleep'
                   WHEN 'SLEEP' THEN 'Sleep'
                   ELSE metric_type::text
               END::vitalmetrictype,
               value, unit, start_date, end_date,
               CASE data_source
                   WHEN 'APPLE_HEALTHKIT' THEN 'apple_healthkit'
                   WHEN 'MANUAL_ENTRY' THEN 'manual_entry'
                   WHEN 'DOCUMENT_EXTRACTION' THEN 'document_extraction'
                   WHEN 'DEVICE_SYNC' THEN 'device_sync'
                   WHEN 'API_IMPORT' THEN 'api_import'
                   ELSE data_source::text
               END::vitaldatasource,
               source_device, notes, confidence_score, created_at, updated_at
        FROM vitals_raw_data
        WHERE EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'vitals_raw_data')
    """)
    
    # Drop old table and rename new one
    op.execute('DROP TABLE IF EXISTS vitals_raw_data')
    op.execute('ALTER TABLE vitals_raw_data_new RENAME TO vitals_raw_data')
    
    # Recreate indexes
    op.create_index('idx_vitals_raw_user_metric_date', 'vitals_raw_data', ['user_id', 'metric_type', 'start_date'])
    op.create_index('idx_vitals_raw_user_date', 'vitals_raw_data', ['user_id', 'start_date'])
    op.create_index('idx_vitals_raw_data_source', 'vitals_raw_data', ['data_source'])

def downgrade():
    # This would revert back to the old enum format
    # Drop tables
    op.drop_table('vitals_raw_data')
    
    # Drop enum types
    op.execute('DROP TYPE vitaldatasource')
    op.execute('DROP TYPE vitalmetrictype')
    
    # Recreate old enums (this is the downgrade path)
    vital_metric_type = postgresql.ENUM(
        'HEART_RATE', 'BLOOD_PRESSURE_SYSTOLIC', 'BLOOD_PRESSURE_DIASTOLIC',
        'BODY_TEMPERATURE', 'BODY_MASS', 'HEIGHT', 'BMI', 'STEP_COUNT',
        'ACTIVE_ENERGY', 'RESTING_ENERGY', 'EXERCISE_TIME', 'STAND_TIME',
        'SLEEP_ANALYSIS', 'RESPIRATORY_RATE', 'OXYGEN_SATURATION',
        'BLOOD_GLUCOSE', 'BLOOD_PRESSURE', 'WORKOUT_TYPE', 'DISTANCE_WALKING_RUNNING',
        'FLIGHTS_CLIMBED', 'APPLE_EXERCISE_TIME', 'APPLE_STAND_TIME',
        'ENVIRONMENTAL_AUDIO_EXPOSURE', 'HEADPHONE_AUDIO_EXPOSURE',
        'WALKING_DOUBLE_SUPPORT_PERCENTAGE', 'SIX_MINUTE_WALK_TEST_DISTANCE',
        'WALKING_SPEED', 'WALKING_STEP_LENGTH', 'WALKING_ASYMMETRY_PERCENTAGE',
        'STAIR_ASCENT_SPEED', 'STAIR_DESCENT_SPEED', 'BLOOD_SUGAR',
        name='vitalmetrictype'
    )
    vital_metric_type.create(op.get_bind())
    
    vital_data_source = postgresql.ENUM(
        'APPLE_HEALTHKIT', 'MANUAL_ENTRY', 'DOCUMENT_EXTRACTION', 'DEVICE_SYNC', 'API_IMPORT',
        name='vitaldatasource'
    )
    vital_data_source.create(op.get_bind()) 