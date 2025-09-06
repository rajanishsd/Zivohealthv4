"""028_add_nutrition_meal_plans_table

Revision ID: 16c952807f5d
Revises: 3e418eb4725f
Create Date: 2025-09-06 11:49:17.550639

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '16c952807f5d'
down_revision = '3e418eb4725f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create nutrition_meal_plans table
    op.create_table('nutrition_meal_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('goal_id', sa.Integer(), nullable=False),
        sa.Column('meal_type', sa.String(50), nullable=False),  # breakfast, lunch, dinner, snacks
        sa.Column('meal_name', sa.String(200), nullable=False),
        sa.Column('calories_kcal', sa.Integer(), nullable=True),
        sa.Column('protein_g', sa.Float(), nullable=True),
        sa.Column('carbohydrate_g', sa.Float(), nullable=True),
        sa.Column('fat_g', sa.Float(), nullable=True),
        sa.Column('fiber_g', sa.Float(), nullable=True),
        sa.Column('preparation_time_min', sa.Integer(), nullable=True),
        sa.Column('difficulty', sa.String(20), nullable=True),  # Easy, Medium, Hard
        sa.Column('ingredients', sa.Text(), nullable=True),  # JSON array of ingredients
        sa.Column('micronutrients', sa.Text(), nullable=True),  # JSON object of micronutrients
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_recommended', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['goal_id'], ['nutrition_goals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index on goal_id for faster queries
    op.create_index('ix_nutrition_meal_plans_goal_id', 'nutrition_meal_plans', ['goal_id'])
    
    # Create index on meal_type for filtering
    op.create_index('ix_nutrition_meal_plans_meal_type', 'nutrition_meal_plans', ['meal_type'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_nutrition_meal_plans_meal_type', table_name='nutrition_meal_plans')
    op.drop_index('ix_nutrition_meal_plans_goal_id', table_name='nutrition_meal_plans')
    
    # Drop table
    op.drop_table('nutrition_meal_plans') 