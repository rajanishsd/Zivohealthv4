"""merge heads for dual auth

Revision ID: d5bed3016eb0
Revises: 034_add_user_identities_and_login_events, 031_add_goal_id_to_user_nutrient_focus
Create Date: 2025-09-11 12:22:50.993522

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd5bed3016eb0'
down_revision = ('034_add_user_identities_and_login_events', '031_add_goal_id_to_user_nutrient_focus')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass 