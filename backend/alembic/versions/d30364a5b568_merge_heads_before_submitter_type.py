"""merge heads before submitter_type

Revision ID: d30364a5b568
Revises: 9c3732733048, 043_add_app_identifier
Create Date: 2025-10-01 14:58:33.250213

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd30364a5b568'
down_revision = ('9c3732733048', '043_add_app_identifier')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass 