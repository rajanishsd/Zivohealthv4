"""remove name fields from users table

Revision ID: 052_remove_name_fields_from_users
Revises: 051_add_timezone_dictionary
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '052'
down_revision = '051_add_timezone_dictionary'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove name fields from users table
    op.drop_column('users', 'first_name')
    op.drop_column('users', 'middle_name')
    op.drop_column('users', 'last_name')


def downgrade() -> None:
    # Add name fields back to users table
    op.add_column('users', sa.Column('first_name', sa.String(), nullable=True))
    op.add_column('users', sa.Column('middle_name', sa.String(), nullable=True))
    op.add_column('users', sa.Column('last_name', sa.String(), nullable=True))
