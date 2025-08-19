"""add_user_id_to_pharmacy_medications

Revision ID: 017
Revises: 016
Create Date: 2025-01-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '017'
down_revision = '016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add user_id column to pharmacy_medications table
    op.add_column('pharmacy_medications', 
                  sa.Column('user_id', sa.Integer(), nullable=False))
    
    # Add foreign key constraint to users table
    op.create_foreign_key('fk_pharmacy_medications_user_id', 
                         'pharmacy_medications', 
                         'users', 
                         ['user_id'], 
                         ['id'])
    
    # Add index for efficient user-based queries
    op.create_index('ix_pharmacy_medications_user_id', 
                   'pharmacy_medications', 
                   ['user_id'])


def downgrade() -> None:
    # Remove index
    op.drop_index('ix_pharmacy_medications_user_id', 'pharmacy_medications')
    
    # Remove foreign key constraint
    op.drop_constraint('fk_pharmacy_medications_user_id', 
                      'pharmacy_medications', 
                      type_='foreignkey')
    
    # Remove user_id column
    op.drop_column('pharmacy_medications', 'user_id') 