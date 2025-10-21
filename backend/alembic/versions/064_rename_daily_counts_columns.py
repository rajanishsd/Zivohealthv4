"""rename daily aggregate columns to counts and drop top3 semantics

Revision ID: 064
Revises: 063
Create Date: 2025-10-14 16:36:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '064'
down_revision = '063'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('mental_health_daily') as batch_op:
        try:
            batch_op.alter_column('feelings_top3_json', new_column_name='feelings_counts_json')
        except Exception:
            pass
        try:
            batch_op.alter_column('impacts_top3_json', new_column_name='impacts_counts_json')
        except Exception:
            pass


def downgrade() -> None:
    with op.batch_alter_table('mental_health_daily') as batch_op:
        try:
            batch_op.alter_column('feelings_counts_json', new_column_name='feelings_top3_json')
        except Exception:
            pass
        try:
            batch_op.alter_column('impacts_counts_json', new_column_name='impacts_top3_json')
        except Exception:
            pass


