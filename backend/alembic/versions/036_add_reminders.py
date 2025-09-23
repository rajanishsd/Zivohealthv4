"""add reminders table

Revision ID: 036_add_reminders
Revises: 035_add_onboarding
Create Date: 2025-09-17
"""

from alembic import op
import sqlalchemy as sa
import uuid


# revision identifiers, used by Alembic.
revision = '036_add_reminders'
down_revision = '035_add_onboarding'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'reminders',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('reminder_type', sa.String(), nullable=False),
        sa.Column('reminder_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('payload', sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('status', sa.String(), nullable=False, server_default='Pending'),
        sa.Column('external_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_reminders_status_time', 'reminders', ['status', 'reminder_time'])
    op.create_index('ix_reminders_user_time', 'reminders', ['user_id', 'reminder_time'])


def downgrade() -> None:
    op.drop_index('ix_reminders_user_time', table_name='reminders')
    op.drop_index('ix_reminders_status_time', table_name='reminders')
    op.drop_table('reminders')


