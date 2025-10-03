"""merge heads after admin

Revision ID: d830f765b5ee
Revises: 042_add_admin_table, 116081bc4db5
Create Date: 2025-10-01 13:54:41.141139

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd830f765b5ee'
down_revision = ('042_add_admin_table', '116081bc4db5')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass 