"""030_modify_meal_plans_to_store_json_strings

Revision ID: 0677399a8cd8
Revises: 16c952807f5d
Create Date: 2025-09-06 13:01:33.556706

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0677399a8cd8'
down_revision = '16c952807f5d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the existing nutrition_meal_plans table
    op.drop_table('nutrition_meal_plans')
    
    # Create new nutrition_meal_plans table with simplified structure
    op.create_table('nutrition_meal_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('goal_id', sa.Integer(), nullable=False),
        sa.Column('breakfast', sa.Text(), nullable=True),  # JSON string
        sa.Column('lunch', sa.Text(), nullable=True),  # JSON string
        sa.Column('dinner', sa.Text(), nullable=True),  # JSON string
        sa.Column('snacks', sa.Text(), nullable=True),  # JSON string
        sa.Column('recommended_options', sa.Text(), nullable=True),  # JSON string
        sa.Column('total_calories_kcal', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['goal_id'], ['nutrition_goals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index on goal_id for faster queries
    op.create_index('ix_nutrition_meal_plans_goal_id', 'nutrition_meal_plans', ['goal_id'])


def downgrade() -> None:
    # Drop the new table
    op.drop_index('ix_nutrition_meal_plans_goal_id', table_name='nutrition_meal_plans')
    op.drop_table('nutrition_meal_plans')
    
    # Recreate the original table structure
    op.create_table('nutrition_meal_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('goal_id', sa.Integer(), nullable=False),
        sa.Column('meal_type', sa.String(50), nullable=False),
        sa.Column('meal_name', sa.String(200), nullable=False),
        sa.Column('calories_kcal', sa.Integer(), nullable=True),
        sa.Column('protein_g', sa.Float(), nullable=True),
        sa.Column('carbohydrate_g', sa.Float(), nullable=True),
        sa.Column('fat_g', sa.Float(), nullable=True),
        sa.Column('fiber_g', sa.Float(), nullable=True),
        sa.Column('preparation_time_min', sa.Integer(), nullable=True),
        sa.Column('difficulty', sa.String(20), nullable=True),
        sa.Column('ingredients', sa.Text(), nullable=True),
        sa.Column('micronutrients', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_recommended', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['goal_id'], ['nutrition_goals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_nutrition_meal_plans_goal_id', 'nutrition_meal_plans', ['goal_id'])
    op.create_index('ix_nutrition_meal_plans_meal_type', 'nutrition_meal_plans', ['meal_type']) 