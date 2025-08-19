"""add_timestamps_to_pharmacy_bills

Revision ID: 016
Revises: 015
Create Date: 2025-07-26 17:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '016'
down_revision = '015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fix created_at column to have proper server default and timezone
    op.alter_column('pharmacy_bills', 'created_at',
                   existing_type=sa.DateTime(),
                   type_=sa.DateTime(timezone=True),
                   server_default=sa.func.now(),
                   nullable=False)
    
    # Fix updated_at column to have proper server default and timezone
    op.alter_column('pharmacy_bills', 'updated_at',
                   existing_type=sa.DateTime(),
                   type_=sa.DateTime(timezone=True),
                   server_default=sa.func.now(),
                   nullable=False)


def downgrade() -> None:
    # Revert updated_at column changes
    op.alter_column('pharmacy_bills', 'updated_at',
                   existing_type=sa.DateTime(timezone=True),
                   type_=sa.DateTime(),
                   server_default=None,
                   nullable=True)
    
    # Revert created_at column changes
    op.alter_column('pharmacy_bills', 'created_at',
                   existing_type=sa.DateTime(timezone=True),
                   type_=sa.DateTime(),
                   server_default=None,
                   nullable=True) 