"""merge heads after adding user_devices

Revision ID: 048_merge_heads
Revises: 2f8bb57731ea, 047_add_user_devices
Create Date: 2025-10-06
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '048_merge_heads'
down_revision = ('2f8bb57731ea', '047_add_user_devices')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass


