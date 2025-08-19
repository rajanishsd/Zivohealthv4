"""merge_heads

Revision ID: 500ad6b623e7
Revises: 013_loincagg, f85776b77d85
Create Date: 2025-07-13 17:16:13.878410

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '500ad6b623e7'
down_revision = ('013_loincagg', 'f85776b77d85')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass 