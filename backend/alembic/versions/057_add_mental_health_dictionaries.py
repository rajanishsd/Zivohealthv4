"""add mental health feeling/impact dictionaries

Revision ID: 057
Revises: 056
Create Date: 2025-10-14 12:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '057'
down_revision = '056'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'mental_health_feelings_dictionary',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('is_active', sa.String(), nullable=False, server_default='true'),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_mh_feelings_name')
    )
    op.create_index('ix_mh_feelings_name', 'mental_health_feelings_dictionary', ['name'], unique=False)

    op.create_table(
        'mental_health_impacts_dictionary',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('is_active', sa.String(), nullable=False, server_default='true'),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_mh_impacts_name')
    )
    op.create_index('ix_mh_impacts_name', 'mental_health_impacts_dictionary', ['name'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_mh_impacts_name', table_name='mental_health_impacts_dictionary')
    op.drop_table('mental_health_impacts_dictionary')
    op.drop_index('ix_mh_feelings_name', table_name='mental_health_feelings_dictionary')
    op.drop_table('mental_health_feelings_dictionary')


