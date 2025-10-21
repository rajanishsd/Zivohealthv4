"""add aggregation status to mental_health_entries

Revision ID: 063
Revises: 062
Create Date: 2025-10-14 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '063'
down_revision = '062'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('mental_health_entries') as batch_op:
        batch_op.add_column(sa.Column('aggregation_status', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('aggregated_at', sa.DateTime(), nullable=True))
        batch_op.create_index('ix_mh_entries_aggregation_status', ['aggregation_status'])


def downgrade() -> None:
    with op.batch_alter_table('mental_health_entries') as batch_op:
        batch_op.drop_index('ix_mh_entries_aggregation_status')
        batch_op.drop_column('aggregated_at')
        batch_op.drop_column('aggregation_status')


