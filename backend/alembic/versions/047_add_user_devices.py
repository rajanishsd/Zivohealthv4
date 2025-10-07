"""add user_devices table

Revision ID: 047_add_user_devices
Revises: 046_add_user_deletion_fields
Create Date: 2025-10-06
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '047_add_user_devices'
down_revision = '046_add_user_deletion_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_devices',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('provider', sa.String(length=64), nullable=False, index=True),  # e.g., 'healthkit'
        sa.Column('device_name', sa.String(length=128), nullable=False),          # e.g., 'Apple HealthKit'
        sa.Column('is_connected', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('connected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('disconnected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('device_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_user_devices_user_provider', 'user_devices', ['user_id', 'provider'])
    op.create_unique_constraint('uq_user_devices_user_provider_name', 'user_devices', ['user_id', 'provider', 'device_name'])


def downgrade() -> None:
    op.drop_constraint('uq_user_devices_user_provider_name', 'user_devices', type_='unique')
    op.drop_index('ix_user_devices_user_provider', table_name='user_devices')
    op.drop_table('user_devices')


