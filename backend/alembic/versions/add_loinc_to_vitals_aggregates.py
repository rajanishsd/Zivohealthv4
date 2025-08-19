"""add_loinc_code_to_vitals_aggregates

Revision ID: add_loinc_to_vitals_aggregates
Revises: add_unique_vitals_categorized
Create Date: 2025-07-13 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_loinc_to_vitals_aggregates'
down_revision = 'add_unique_vitals_categorized'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add loinc_code column to vitals_hourly_aggregates table
    op.add_column('vitals_hourly_aggregates', sa.Column('loinc_code', sa.String(20), nullable=True))
    op.create_index('idx_loinc_code_hourly', 'vitals_hourly_aggregates', ['loinc_code'])
    
    # Add loinc_code column to vitals_daily_aggregates table
    op.add_column('vitals_daily_aggregates', sa.Column('loinc_code', sa.String(20), nullable=True))
    op.create_index('idx_loinc_code_daily', 'vitals_daily_aggregates', ['loinc_code'])
    
    # Add loinc_code column to vitals_weekly_aggregates table
    op.add_column('vitals_weekly_aggregates', sa.Column('loinc_code', sa.String(20), nullable=True))
    op.create_index('idx_loinc_code_weekly', 'vitals_weekly_aggregates', ['loinc_code'])
    
    # Add loinc_code column to vitals_monthly_aggregates table
    op.add_column('vitals_monthly_aggregates', sa.Column('loinc_code', sa.String(20), nullable=True))
    op.create_index('idx_loinc_code_monthly', 'vitals_monthly_aggregates', ['loinc_code'])
    
    # Create new indexes that use loinc_code (keep old indexes for backward compatibility)
    op.create_index('idx_user_loinc_hourly', 'vitals_hourly_aggregates', ['user_id', 'loinc_code', 'hour_start'])
    op.create_index('idx_hour_loinc', 'vitals_hourly_aggregates', ['hour_start', 'loinc_code'])
    op.create_index('idx_user_loinc_daily', 'vitals_daily_aggregates', ['user_id', 'loinc_code', 'date'])
    op.create_index('idx_date_loinc', 'vitals_daily_aggregates', ['date', 'loinc_code'])
    op.create_index('idx_user_loinc_weekly', 'vitals_weekly_aggregates', ['user_id', 'loinc_code', 'week_start_date'])
    op.create_index('idx_user_loinc_monthly', 'vitals_monthly_aggregates', ['user_id', 'loinc_code', 'year', 'month'])


def downgrade() -> None:
    # Drop new indexes
    op.drop_index('idx_user_loinc_hourly', table_name='vitals_hourly_aggregates')
    op.drop_index('idx_hour_loinc', table_name='vitals_hourly_aggregates')
    op.drop_index('idx_user_loinc_daily', table_name='vitals_daily_aggregates')
    op.drop_index('idx_date_loinc', table_name='vitals_daily_aggregates')
    op.drop_index('idx_user_loinc_weekly', table_name='vitals_weekly_aggregates')
    op.drop_index('idx_user_loinc_monthly', table_name='vitals_monthly_aggregates')
    
    # Drop loinc_code columns
    op.drop_index('idx_loinc_code_monthly', table_name='vitals_monthly_aggregates')
    op.drop_column('vitals_monthly_aggregates', 'loinc_code')
    op.drop_index('idx_loinc_code_weekly', table_name='vitals_weekly_aggregates')
    op.drop_column('vitals_weekly_aggregates', 'loinc_code')
    op.drop_index('idx_loinc_code_daily', table_name='vitals_daily_aggregates')
    op.drop_column('vitals_daily_aggregates', 'loinc_code')
    op.drop_index('idx_loinc_code_hourly', table_name='vitals_hourly_aggregates')
    op.drop_column('vitals_hourly_aggregates', 'loinc_code') 