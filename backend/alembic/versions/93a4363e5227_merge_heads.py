"""merge_heads

Revision ID: 93a4363e5227
Revises: d30364a5b568, 045_add_closed_date_to_feedback
Create Date: 2025-10-03 11:00:36.276300

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '93a4363e5227'
down_revision = ('d30364a5b568', '045_add_closed_date_to_feedback')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass 