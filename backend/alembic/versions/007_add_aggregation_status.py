"""Add aggregation status tracking to vitals_raw_data

Revision ID: 007_add_aggregation_status
Revises: 006_fix_vitals_enum_values
Create Date: 2025-01-18 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '007_add_aggregation_status'
down_revision = '006_fix_vitals_enum_values'
branch_labels = None
depends_on = None


def upgrade():
    # Add aggregation_status column with default 'completed' for existing data
    op.add_column('vitals_raw_data', sa.Column('aggregation_status', sa.String(20), nullable=False, server_default='completed'))
    
    # Add aggregated_at timestamp column
    op.add_column('vitals_raw_data', sa.Column('aggregated_at', sa.DateTime(), nullable=True))
    
    # Create index for efficient querying of aggregation status
    op.create_index('idx_aggregation_status', 'vitals_raw_data', ['aggregation_status', 'user_id', 'start_date'])
    
    # Update existing records to have aggregated_at timestamp
    op.execute("UPDATE vitals_raw_data SET aggregated_at = updated_at WHERE aggregation_status = 'completed'")


def downgrade():
    # Drop index
    op.drop_index('idx_aggregation_status', table_name='vitals_raw_data')
    
    # Drop columns
    op.drop_column('vitals_raw_data', 'aggregated_at')
    op.drop_column('vitals_raw_data', 'aggregation_status') 