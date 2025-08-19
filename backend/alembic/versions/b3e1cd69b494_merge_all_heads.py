"""merge_all_heads

Revision ID: b3e1cd69b494
Revises: 2b0297afa5c8, add_loinc_to_vitals_aggregates
Create Date: 2025-07-20 12:46:10.454177

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b3e1cd69b494'
down_revision = ('2b0297afa5c8', 'add_loinc_to_vitals_aggregates')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass 