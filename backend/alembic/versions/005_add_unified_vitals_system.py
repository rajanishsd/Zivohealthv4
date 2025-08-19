"""Add unified vitals system

Revision ID: 005_add_unified_vitals_system
Revises: 004_add_health_data_tables
Create Date: 2025-01-11 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_add_unified_vitals_system'
down_revision = '1832851c1af5'
branch_labels = None
depends_on = None

def upgrade():
    # Create enum types
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
    
    # Create vitals_raw_data table
    op.create_table('vitals_raw_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('metric_type', sa.Enum('HEART_RATE', 'BLOOD_PRESSURE_SYSTOLIC', 'BLOOD_PRESSURE_DIASTOLIC', 'BODY_TEMPERATURE', 'BODY_MASS', 'HEIGHT', 'BMI', 'STEP_COUNT', 'ACTIVE_ENERGY', 'RESTING_ENERGY', 'EXERCISE_TIME', 'STAND_TIME', 'SLEEP_ANALYSIS', 'RESPIRATORY_RATE', 'OXYGEN_SATURATION', 'BLOOD_GLUCOSE', 'BLOOD_PRESSURE', 'WORKOUT_TYPE', 'DISTANCE_WALKING_RUNNING', 'FLIGHTS_CLIMBED', 'APPLE_EXERCISE_TIME', 'APPLE_STAND_TIME', 'ENVIRONMENTAL_AUDIO_EXPOSURE', 'HEADPHONE_AUDIO_EXPOSURE', 'WALKING_DOUBLE_SUPPORT_PERCENTAGE', 'SIX_MINUTE_WALK_TEST_DISTANCE', 'WALKING_SPEED', 'WALKING_STEP_LENGTH', 'WALKING_ASYMMETRY_PERCENTAGE', 'STAIR_ASCENT_SPEED', 'STAIR_DESCENT_SPEED', 'BLOOD_SUGAR', name='vitalmetrictype'), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=50), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=False),
        sa.Column('data_source', sa.Enum('APPLE_HEALTHKIT', 'MANUAL_ENTRY', 'DOCUMENT_EXTRACTION', 'DEVICE_SYNC', 'API_IMPORT', name='vitaldatasource'), nullable=False),
        sa.Column('source_device', sa.String(length=255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_vitals_raw_user_metric_date', 'vitals_raw_data', ['user_id', 'metric_type', 'start_date'])
    op.create_index('idx_vitals_raw_user_date', 'vitals_raw_data', ['user_id', 'start_date'])
    op.create_index('idx_vitals_raw_data_source', 'vitals_raw_data', ['data_source'])

def downgrade():
    # Drop tables
    op.drop_table('vitals_raw_data')
    
    # Drop enum types
    op.execute('DROP TYPE vitaldatasource')
    op.execute('DROP TYPE vitalmetrictype') 