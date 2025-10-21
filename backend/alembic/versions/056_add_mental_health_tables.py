"""add mental health tables

Revision ID: 056
Revises: 055
Create Date: 2025-10-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '056'
down_revision = '055'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'mental_health_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(), nullable=False),
        sa.Column('entry_type', sa.String(), nullable=False),
        sa.Column('pleasantness_score', sa.Integer(), nullable=False),
        sa.Column('pleasantness_label', sa.String(), nullable=False),
        sa.Column('feelings_json', sa.Text(), nullable=True),
        sa.Column('impacts_json', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('source', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_mh_user_recorded_at', 'mental_health_entries', ['user_id', 'recorded_at'], unique=False)

    op.create_table(
        'mental_health_daily',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('avg_score', sa.Integer(), nullable=True),
        sa.Column('last_score', sa.Integer(), nullable=True),
        sa.Column('last_entry_at', sa.DateTime(), nullable=True),
        sa.Column('feelings_top3_json', sa.Text(), nullable=True),
        sa.Column('impacts_top3_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_mh_user_date', 'mental_health_daily', ['user_id', 'date'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_mh_user_date', table_name='mental_health_daily')
    op.drop_table('mental_health_daily')
    op.drop_index('idx_mh_user_recorded_at', table_name='mental_health_entries')
    op.drop_table('mental_health_entries')


