"""
Add loinc_code column to lab aggregation tables

Revision ID: 012
Revises: 011
Create Date: 2025-07-13
"""
from alembic import op
import sqlalchemy as sa

revision = '013_loincagg'
down_revision = '012_add_clinical_reports'
branch_labels = None
depends_on = None

def upgrade():
    # Add loinc_code column to all aggregation tables
    for table in [
        'lab_reports_daily',
        'lab_reports_monthly',
        'lab_reports_quarterly',
        'lab_reports_yearly',
    ]:
        op.add_column(table, sa.Column('loinc_code', sa.String(length=20), nullable=True))
        op.create_index(f'idx_{table}_loinc_code', table, ['loinc_code'])

    # Drop old unique constraints and add new ones including loinc_code
    op.drop_constraint('lab_reports_daily_unique', 'lab_reports_daily', type_='unique')
    op.create_unique_constraint('lab_reports_daily_loinc_code_unique', 'lab_reports_daily', ['user_id', 'date', 'test_category', 'loinc_code'])

    op.drop_constraint('lab_reports_monthly_test_code_unique', 'lab_reports_monthly', type_='unique')
    op.create_unique_constraint('lab_reports_monthly_loinc_code_unique', 'lab_reports_monthly', ['user_id', 'year', 'month', 'test_category', 'loinc_code'])

    op.drop_constraint('lab_reports_quarterly_test_code_unique', 'lab_reports_quarterly', type_='unique')
    op.create_unique_constraint('lab_reports_quarterly_loinc_code_unique', 'lab_reports_quarterly', ['user_id', 'year', 'quarter', 'test_category', 'loinc_code'])

    op.drop_constraint('lab_reports_yearly_test_code_unique', 'lab_reports_yearly', type_='unique')
    op.create_unique_constraint('lab_reports_yearly_loinc_code_unique', 'lab_reports_yearly', ['user_id', 'year', 'test_category', 'loinc_code'])

def downgrade():
    # Remove loinc_code unique constraints and indexes, drop column
    for table, old_uc in [
        ('lab_reports_daily', 'lab_reports_daily_unique'),
        ('lab_reports_monthly', 'lab_reports_monthly_test_code_unique'),
        ('lab_reports_quarterly', 'lab_reports_quarterly_test_code_unique'),
        ('lab_reports_yearly', 'lab_reports_yearly_test_code_unique'),
    ]:
        op.drop_index(f'idx_{table}_loinc_code', table_name=table)
        op.drop_column(table, 'loinc_code')

    # Restore old unique constraints
    op.create_unique_constraint('lab_reports_daily_unique', 'lab_reports_daily', ['user_id', 'date', 'test_category', 'test_name'])
    op.create_unique_constraint('lab_reports_monthly_test_code_unique', 'lab_reports_monthly', ['user_id', 'year', 'month', 'test_category', 'test_code'])
    op.create_unique_constraint('lab_reports_quarterly_test_code_unique', 'lab_reports_quarterly', ['user_id', 'year', 'quarter', 'test_category', 'test_code'])
    op.create_unique_constraint('lab_reports_yearly_test_code_unique', 'lab_reports_yearly', ['user_id', 'year', 'test_category', 'test_code']) 