"""
038 add onboarding_status to user_profiles

Revision ID: 038_add_onboarding_status_to_user_profiles
Revises: 037_add_device_tokens
Create Date: 2025-09-17
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '038_add_onboarding_status'
down_revision = '037_add_device_tokens'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('user_profiles', sa.Column('onboarding_status', sa.String(length=24), nullable=True))


def downgrade() -> None:
    op.drop_column('user_profiles', 'onboarding_status')


