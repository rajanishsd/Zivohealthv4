"""Add scheduled deletion fields to users

Revision ID: 046_add_user_deletion_fields
Revises: 045_add_closed_date_to_feedback
Create Date: 2025-10-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '046_add_user_deletion_fields'
down_revision = '045_add_closed_date_to_feedback'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('is_tobe_deleted', sa.Boolean(), nullable=True, server_default=sa.text('false')))
    op.add_column('users', sa.Column('delete_date', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'delete_date')
    op.drop_column('users', 'is_tobe_deleted')


