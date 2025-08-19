"""Add enhanced_mode_enabled to chat_sessions

Revision ID: 019
Revises: 018
Create Date: 2024-12-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '019'
down_revision = '018'
branch_labels = None
depends_on = None


def upgrade():
    # Add enhanced_mode_enabled column to chat_sessions table
    op.add_column('chat_sessions', sa.Column('enhanced_mode_enabled', sa.Boolean(), nullable=False, server_default='true'))


def downgrade():
    # Remove enhanced_mode_enabled column from chat_sessions table
    op.drop_column('chat_sessions', 'enhanced_mode_enabled')