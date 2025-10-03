"""add feedback_screenshots table

Revision ID: 041_add_feedback_screenshots
Revises: 040_add_user_reminder_configs
Create Date: 2025-10-01
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '041_add_feedback_screenshots'
down_revision = '040_add_user_reminder_configs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'feedback_screenshots',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('s3_key', sa.String(length=500), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('route', sa.String(length=200), nullable=True),
        sa.Column('app_version', sa.String(length=50), nullable=True),
        sa.Column('build_number', sa.String(length=50), nullable=True),
        sa.Column('platform', sa.String(length=20), nullable=True),
        sa.Column('os_version', sa.String(length=50), nullable=True),
        sa.Column('device_model', sa.String(length=120), nullable=True),
        sa.Column('app_identifier', sa.String(length=200), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default=sa.text("'open'")),
        sa.Column('extra', sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_feedback_screenshots_user', 'feedback_screenshots', ['user_id'])
    op.create_index('ix_feedback_screenshots_status', 'feedback_screenshots', ['status'])


def downgrade() -> None:
    op.drop_index('ix_feedback_screenshots_status', table_name='feedback_screenshots')
    op.drop_index('ix_feedback_screenshots_user', table_name='feedback_screenshots')
    op.drop_table('feedback_screenshots')


