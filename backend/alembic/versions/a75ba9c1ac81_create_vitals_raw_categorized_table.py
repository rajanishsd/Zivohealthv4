"""create_vitals_raw_categorized_table

Revision ID: a75ba9c1ac81
Revises: 5b6ec0991a87
Create Date: 2025-07-13 17:25:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a75ba9c1ac81'
down_revision = '013_loincagg'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create vitals_raw_categorized table
    op.create_table('vitals_raw_categorized',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('metric_type', sa.String(), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=False),
        sa.Column('data_source', sa.String(), nullable=False),
        sa.Column('source_device', sa.String(), nullable=True),
        sa.Column('loinc_code', sa.String(20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('aggregation_status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('aggregated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_user_metric_date_categorized', 'vitals_raw_categorized', ['user_id', 'metric_type', 'start_date'])
    op.create_index('idx_metric_date_range_categorized', 'vitals_raw_categorized', ['metric_type', 'start_date', 'end_date'])
    op.create_index('idx_user_source_date_categorized', 'vitals_raw_categorized', ['user_id', 'data_source', 'start_date'])
    op.create_index('idx_aggregation_status_categorized', 'vitals_raw_categorized', ['aggregation_status', 'user_id', 'start_date'])
    op.create_index('idx_loinc_code_categorized', 'vitals_raw_categorized', ['loinc_code'])


def downgrade() -> None:
    # Drop vitals_raw_categorized table
    op.drop_index('idx_loinc_code_categorized', table_name='vitals_raw_categorized')
    op.drop_index('idx_aggregation_status_categorized', table_name='vitals_raw_categorized')
    op.drop_index('idx_user_source_date_categorized', table_name='vitals_raw_categorized')
    op.drop_index('idx_metric_date_range_categorized', table_name='vitals_raw_categorized')
    op.drop_index('idx_user_metric_date_categorized', table_name='vitals_raw_categorized')
    op.drop_table('vitals_raw_categorized') 