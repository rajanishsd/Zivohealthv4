"""add nutrition goals related tables

Revision ID: 024_add_nutrition_goals_tables
Revises: dbfc12478a54
Create Date: 2025-09-03 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = '024_add_nutrition_goals_tables'
down_revision: Union[str, None] = '021'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'nutrition_objectives',
        sa.Column('code', sa.String(), primary_key=True),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'nutrition_nutrient_catalog',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key', sa.String(), nullable=False, unique=True),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('unit', sa.String(), nullable=False),
        sa.Column('rda_male', sa.Float(), nullable=True),
        sa.Column('rda_female', sa.Float(), nullable=True),
        sa.Column('upper_limit', sa.Float(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('aggregate_field', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'nutrition_goals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('objective_code', sa.String(), sa.ForeignKey('nutrition_objectives.code'), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        sa.Column('effective_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('idx_nutrition_goal_user_status', 'nutrition_goals', ['user_id', 'status'], unique=False)
    op.create_index('idx_nutrition_goal_user_objective_status', 'nutrition_goals', ['user_id', 'objective_code', 'status'], unique=False)

    op.create_table(
        'nutrition_goal_targets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('goal_id', sa.Integer(), sa.ForeignKey('nutrition_goals.id'), nullable=False),
        sa.Column('nutrient_id', sa.Integer(), sa.ForeignKey('nutrition_nutrient_catalog.id'), nullable=False),
        sa.Column('timeframe', sa.String(), nullable=False),
        sa.Column('target_type', sa.String(), nullable=False),
        sa.Column('target_min', sa.Float(), nullable=True),
        sa.Column('target_max', sa.Float(), nullable=True),
        sa.Column('priority', sa.String(), nullable=False, server_default='secondary'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('goal_id', 'nutrient_id', 'timeframe', name='uq_goal_nutrient_timeframe'),
    )
    op.create_index('idx_goal_target_goal', 'nutrition_goal_targets', ['goal_id'], unique=False)
    op.create_index('idx_goal_target_nutrient', 'nutrition_goal_targets', ['nutrient_id'], unique=False)

    op.create_table(
        'user_nutrient_focus',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('nutrient_id', sa.Integer(), sa.ForeignKey('nutrition_nutrient_catalog.id'), nullable=False),
        sa.Column('priority', sa.String(), nullable=False, server_default='secondary'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('user_id', 'nutrient_id', name='uq_user_nutrient'),
    )
    op.create_index('idx_user_nutrient_focus_user', 'user_nutrient_focus', ['user_id'], unique=False)
    op.create_index('idx_user_nutrient_focus_nutrient', 'user_nutrient_focus', ['nutrient_id'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_user_nutrient_focus_nutrient', table_name='user_nutrient_focus')
    op.drop_index('idx_user_nutrient_focus_user', table_name='user_nutrient_focus')
    op.drop_table('user_nutrient_focus')

    op.drop_index('idx_goal_target_nutrient', table_name='nutrition_goal_targets')
    op.drop_index('idx_goal_target_goal', table_name='nutrition_goal_targets')
    op.drop_table('nutrition_goal_targets')

    op.drop_index('idx_nutrition_goal_user_objective_status', table_name='nutrition_goals')
    op.drop_index('idx_nutrition_goal_user_status', table_name='nutrition_goals')
    op.drop_table('nutrition_goals')

    op.drop_table('nutrition_nutrient_catalog')
    op.drop_table('nutrition_objectives')


