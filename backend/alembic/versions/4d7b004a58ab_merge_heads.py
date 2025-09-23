"""merge_heads

Revision ID: 4d7b004a58ab
Revises: 90d1fbcd5617, 038_add_onboarding_status
Create Date: 2025-09-18 21:08:36.256643

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4d7b004a58ab'
down_revision = ('90d1fbcd5617', '038_add_onboarding_status')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass 