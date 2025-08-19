"""Add visualizations column to chat_messages

Revision ID: 022
Revises: 021
Create Date: 2025-08-04 14:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '022'
down_revision = '021'
branch_labels = None
depends_on = None


def upgrade():
    # Add visualizations column to chat_messages table
    op.add_column('chat_messages', sa.Column('visualizations', postgresql.JSON(), nullable=True))


def downgrade():
    # Remove visualizations column from chat_messages table
    op.drop_column('chat_messages', 'visualizations')