"""Add unique constraint to vitals raw data to prevent duplicates

Revision ID: 011_add_vitals_unique_constraint
Revises: 010_add_lab_test_mapping_table
Create Date: 2025-01-27 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '011_add_vitals_unique_constraint'
down_revision = '010_add_lab_test_mapping_table'
branch_labels = None
depends_on = None


def upgrade():
    """Add unique constraint to prevent duplicate vitals data"""
    
    # First, remove any existing duplicates before adding the constraint
    # This query will keep only the earliest record for each duplicate group
    op.execute("""
        DELETE FROM vitals_raw_data 
        WHERE id NOT IN (
            SELECT min_id FROM (
                SELECT MIN(id) as min_id
                FROM vitals_raw_data 
                GROUP BY user_id, metric_type, unit, start_date, data_source, COALESCE(notes, '')
            ) AS keeper_ids
        )
    """)
    
    # Add the unique constraint
    op.create_unique_constraint(
        'uq_vitals_raw_data_no_duplicates',
        'vitals_raw_data',
        ['user_id', 'metric_type', 'unit', 'start_date', 'data_source', 'notes']
    )


def downgrade():
    """Remove the unique constraint"""
    op.drop_constraint('uq_vitals_raw_data_no_duplicates', 'vitals_raw_data', type_='unique') 