"""merge heads for nutrition goals

Revision ID: 9058b1a8b411
Revises: 023, 2c6d1d805586, 024_add_nutrition_goals_tables
Create Date: 2025-09-03 12:15:01.400162

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9058b1a8b411'
down_revision = ('023', '2c6d1d805586', '024_add_nutrition_goals_tables')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass 