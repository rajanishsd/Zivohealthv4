"""merge_aggregation_status_heads

Revision ID: f85776b77d85
Revises: 007_add_aggregation_status, 870e4ae7a8de
Create Date: 2025-06-18 14:41:00.708022

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f85776b77d85'
down_revision = ('007_add_aggregation_status', '870e4ae7a8de')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass 