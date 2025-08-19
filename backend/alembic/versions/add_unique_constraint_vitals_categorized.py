"""add_unique_constraint_to_vitals_raw_categorized

Revision ID: add_unique_constraint_vitals_categorized
Revises: a75ba9c1ac81
Create Date: 2025-07-13 17:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_unique_vitals_categorized'
down_revision = 'a75ba9c1ac81'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add unique constraint to vitals_raw_categorized table
    op.create_unique_constraint(
        'uq_vitals_raw_categorized_no_duplicates',
        'vitals_raw_categorized',
        ['user_id', 'metric_type', 'unit', 'start_date', 'data_source', 'notes']
    )


def downgrade() -> None:
    # Remove unique constraint from vitals_raw_categorized table
    op.drop_constraint('uq_vitals_raw_categorized_no_duplicates', 'vitals_raw_categorized', type_='unique') 