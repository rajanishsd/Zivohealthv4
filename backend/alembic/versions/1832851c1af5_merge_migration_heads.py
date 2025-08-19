"""merge_migration_heads

Revision ID: 1832851c1af5
Revises: add_missing_tables, add_appointments_table
Create Date: 2025-06-04 16:06:57.590489

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1832851c1af5'
down_revision = ('add_missing_tables', 'add_appointments_table')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass 