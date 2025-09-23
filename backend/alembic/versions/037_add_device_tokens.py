"""add device_tokens table

Revision ID: 037_add_device_tokens
Revises: 036_add_reminders
Create Date: 2025-09-17
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '037_add_device_tokens'
down_revision = '036_add_reminders'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'device_tokens',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('platform', sa.String(), nullable=False),
        sa.Column('fcm_token', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_device_tokens_user_platform', 'device_tokens', ['user_id', 'platform'])
    op.create_index('ix_device_tokens_fcm_token', 'device_tokens', ['fcm_token'])


def downgrade() -> None:
    op.drop_index('ix_device_tokens_fcm_token', table_name='device_tokens')
    op.drop_index('ix_device_tokens_user_platform', table_name='device_tokens')
    op.drop_table('device_tokens')


