"""create health scoring tables

Revision ID: 065
Revises: 064
Create Date: 2025-10-15 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '065'
down_revision = '064'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'health_score_specs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('version', sa.String(length=32), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('spec_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('version', name='uq_health_score_spec_version')
    )
    op.create_index('ix_health_score_specs_default', 'health_score_specs', ['is_default'])

    op.create_table(
        'metric_anchor_registry',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('domain', sa.String(length=32), nullable=False),
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('loinc_code', sa.String(length=20), nullable=True),
        sa.Column('unit', sa.String(length=32), nullable=True),
        sa.Column('pattern', sa.String(length=24), nullable=False),
        sa.Column('anchors', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('half_life_days', sa.Integer(), nullable=True),
        sa.Column('danger', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('group_key', sa.String(length=64), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('introduced_in', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('domain', 'key', name='uq_metric_anchor_domain_key')
    )
    op.create_index('idx_metric_anchor_domain', 'metric_anchor_registry', ['domain'])
    op.create_index('idx_metric_anchor_key', 'metric_anchor_registry', ['key'])
    op.create_index('idx_metric_anchor_loinc', 'metric_anchor_registry', ['loinc_code'])

    op.create_table(
        'health_score_results_daily',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('chronic_score', sa.Float(), nullable=True),
        sa.Column('acute_score', sa.Float(), nullable=True),
        sa.Column('overall_score', sa.Float(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('detail', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('spec_version', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'date', name='uq_health_score_results_daily_user_date')
    )
    op.create_index('idx_health_score_results_daily_user_date', 'health_score_results_daily', ['user_id', 'date'])

    op.create_table(
        'health_score_calculations_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('calculated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('window_start', sa.DateTime(), nullable=True),
        sa.Column('window_end', sa.DateTime(), nullable=True),
        sa.Column('spec_version', sa.String(length=32), nullable=False),
        sa.Column('inputs_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('result_overall', sa.Float(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_health_score_calc_log_user_time', 'health_score_calculations_log', ['user_id', 'calculated_at'])


def downgrade() -> None:
    op.drop_index('idx_health_score_calc_log_user_time', table_name='health_score_calculations_log')
    op.drop_table('health_score_calculations_log')
    op.drop_index('idx_health_score_results_daily_user_date', table_name='health_score_results_daily')
    op.drop_table('health_score_results_daily')
    op.drop_index('idx_metric_anchor_loinc', table_name='metric_anchor_registry')
    op.drop_index('idx_metric_anchor_key', table_name='metric_anchor_registry')
    op.drop_index('idx_metric_anchor_domain', table_name='metric_anchor_registry')
    op.drop_table('metric_anchor_registry')
    op.drop_index('ix_health_score_specs_default', table_name='health_score_specs')
    op.drop_table('health_score_specs')


