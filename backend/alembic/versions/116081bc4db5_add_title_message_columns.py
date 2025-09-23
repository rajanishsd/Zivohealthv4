"""add_title_message_columns

Revision ID: 116081bc4db5
Revises: 039_recurring_unified
Create Date: 2025-09-19 13:26:42.352233

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '116081bc4db5'
down_revision = '039_recurring_unified'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add missing title and message columns
    op.add_column('reminders', sa.Column('title', sa.String, nullable=True))
    op.add_column('reminders', sa.Column('message', sa.String, nullable=True))


def downgrade() -> None:
    # Drop title and message columns
    op.drop_column('reminders', 'message')
    op.drop_column('reminders', 'title') 