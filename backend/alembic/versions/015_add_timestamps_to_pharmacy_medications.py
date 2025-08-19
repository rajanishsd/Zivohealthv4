"""add_timestamps_to_pharmacy_medications

Revision ID: 015
Revises: f5d4a0c31fe9
Create Date: 2025-07-26 17:51:46.001185

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '015'
down_revision = 'f5d4a0c31fe9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fix created_at column to have proper server default
    op.alter_column('pharmacy_medications', 'created_at',
                   existing_type=sa.DateTime(),
                   type_=sa.DateTime(timezone=True),
                   server_default=sa.func.now(),
                   nullable=False)
    
    # Add updated_at column
    op.add_column('pharmacy_medications', 
                  sa.Column('updated_at', 
                           sa.DateTime(timezone=True), 
                           server_default=sa.func.now(), 
                           nullable=False))


def downgrade() -> None:
    # Remove updated_at column
    op.drop_column('pharmacy_medications', 'updated_at')
    
    # Revert created_at column changes
    op.alter_column('pharmacy_medications', 'created_at',
                   existing_type=sa.DateTime(timezone=True),
                   type_=sa.DateTime(),
                   server_default=None,
                   nullable=True) 