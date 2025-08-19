"""add_timestamps_to_prescriptions

Revision ID: f5d4a0c31fe9
Revises: 014
Create Date: 2025-07-26 17:47:29.318642

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f5d4a0c31fe9'
down_revision = '014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add created_at and updated_at columns to prescriptions table
    op.add_column('prescriptions', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.add_column('prescriptions', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade() -> None:
    # Remove created_at and updated_at columns from prescriptions table
    op.drop_column('prescriptions', 'updated_at')
    op.drop_column('prescriptions', 'created_at') 