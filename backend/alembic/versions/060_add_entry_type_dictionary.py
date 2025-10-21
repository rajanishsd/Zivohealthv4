"""add entry type dictionary

Revision ID: 060
Revises: 059
Create Date: 2025-10-14 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '060'
down_revision = '059'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'mental_health_entry_type_dictionary',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('label', sa.String(), nullable=False),
        sa.Column('is_active', sa.String(), nullable=False, server_default='true'),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_mh_entry_type_code')
    )
    op.create_index('ix_mh_entry_type_code', 'mental_health_entry_type_dictionary', ['code'], unique=False)

    # seed default types
    conn = op.get_bind()
    pairs = [
        ('emotion_now', 'Emotion (right now)'),
        ('mood_today', 'Mood (today overall)'),
    ]
    for i, (code, label) in enumerate(pairs):
        conn.execute(sa.text(
            "INSERT INTO mental_health_entry_type_dictionary (code, label, is_active, sort_order)"
            " VALUES (:code, :label, 'true', :sort) ON CONFLICT (code) DO NOTHING"
        ), {"code": code, "label": label, "sort": i})


def downgrade() -> None:
    op.drop_index('ix_mh_entry_type_code', table_name='mental_health_entry_type_dictionary')
    op.drop_table('mental_health_entry_type_dictionary')


