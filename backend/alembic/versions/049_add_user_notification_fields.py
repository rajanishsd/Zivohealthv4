"""
add user notification fields

Revision ID: 049_add_user_notification_fields
Revises: 048_merge_heads
Create Date: 2025-10-06 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '049_add_user_notification_fields'
down_revision = '048_merge_heads'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('notifications_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')))


def downgrade() -> None:
    op.drop_column('users', 'notifications_enabled')


