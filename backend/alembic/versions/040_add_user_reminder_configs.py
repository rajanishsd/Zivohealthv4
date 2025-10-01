"""add user_reminder_configs table

Revision ID: 040_add_user_reminder_configs
Revises: 039_add_unified_recurring_reminders
Create Date: 2025-09-23
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '040_add_user_reminder_configs'
# Merge previous heads into 040 so 040 is the single head
down_revision = ('4d7b004a58ab', '116081bc4db5')
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_reminder_configs',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('context', sa.String(), nullable=False),  # nutrition_goal | prescription
        sa.Column('context_id', sa.String(), nullable=False),
        sa.Column('reminder_type', sa.String(), nullable=False),  # nutrition_log | medication_take
        sa.Column('key', sa.String(), nullable=False),  # breakfast | lunch | dinner | medicationId
        sa.Column('external_id', sa.String(), nullable=False, unique=True),
        sa.Column('group_id', sa.String(), nullable=False),
        sa.Column('config_json', sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_user_reminder_configs_user_ctx', 'user_reminder_configs', ['user_id', 'context', 'context_id'])
    op.create_index('ix_user_reminder_configs_group', 'user_reminder_configs', ['group_id'])


def downgrade() -> None:
    op.drop_index('ix_user_reminder_configs_group', table_name='user_reminder_configs')
    op.drop_index('ix_user_reminder_configs_user_ctx', table_name='user_reminder_configs')
    op.drop_table('user_reminder_configs')


