"""Merge vitals and health data migrations

Revision ID: 870e4ae7a8de
Revises: 005_add_unified_vitals_system, add_health_data_tables
Create Date: 2025-06-17 15:19:47.306074

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '870e4ae7a8de'
down_revision = ('005_add_unified_vitals_system', 'add_health_data_tables')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass 