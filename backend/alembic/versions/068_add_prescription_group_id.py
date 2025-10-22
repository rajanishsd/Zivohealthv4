"""068 add prescription_group_id to prescriptions

Revision ID: 068
Revises: 067
Create Date: 2025-10-22
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '068'
down_revision = '067'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add grouping ID column to prescriptions table
    op.add_column('prescriptions', sa.Column('prescription_group_id', sa.String(length=64), nullable=True))
    # Helpful composite index for user+group queries
    op.create_index('ix_prescriptions_group_user', 'prescriptions', ['prescription_group_id', 'user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_prescriptions_group_user', table_name='prescriptions')
    op.drop_column('prescriptions', 'prescription_group_id')


