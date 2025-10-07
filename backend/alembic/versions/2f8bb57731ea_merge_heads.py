"""merge heads

Revision ID: 2f8bb57731ea
Revises: 93a4363e5227, 046_add_user_deletion_fields
Create Date: 2025-10-06 10:19:16.161762

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2f8bb57731ea'
down_revision = ('93a4363e5227', '046_add_user_deletion_fields')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass 