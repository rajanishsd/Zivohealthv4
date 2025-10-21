"""add pleasantness dictionary

Revision ID: 059
Revises: 058
Create Date: 2025-10-14 12:25:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '059'
down_revision = '058'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'mental_health_pleasantness_dictionary',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(), nullable=False),
        sa.Column('is_active', sa.String(), nullable=False, server_default='true'),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('score', name='uq_mh_pleasantness_score')
    )
    op.create_index('ix_mh_pleasantness_score', 'mental_health_pleasantness_dictionary', ['score'], unique=False)

    # seed default mapping
    conn = op.get_bind()
    pairs = [
        (-3, 'Very Unpleasant'),
        (-2, 'Unpleasant'),
        (-1, 'Slightly Unpleasant'),
        (0, 'Neutral'),
        (1, 'Slightly Pleasant'),
        (2, 'Pleasant'),
        (3, 'Very Pleasant'),
    ]
    for i, (score, label) in enumerate(pairs):
        conn.execute(sa.text(
            "INSERT INTO mental_health_pleasantness_dictionary (score, label, is_active, sort_order)"
            " VALUES (:score, :label, 'true', :sort) ON CONFLICT (score) DO NOTHING"
        ), {"score": score, "label": label, "sort": i})


def downgrade() -> None:
    op.drop_index('ix_mh_pleasantness_score', table_name='mental_health_pleasantness_dictionary')
    op.drop_table('mental_health_pleasantness_dictionary')


