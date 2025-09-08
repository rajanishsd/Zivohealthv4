"""031_add_goal_id_to_user_nutrient_focus

Revision ID: 031_add_goal_id_to_user_nutrient_focus
Revises: 0677399a8cd8
Create Date: 2025-09-06 15:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '031_add_goal_id_to_user_nutrient_focus'
down_revision = '0677399a8cd8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add goal_id column to user_nutrient_focus table
    op.add_column('user_nutrient_focus', sa.Column('goal_id', sa.Integer(), nullable=True))
    
    # Add foreign key constraint
    op.create_foreign_key('fk_user_nutrient_focus_goal_id', 'user_nutrient_focus', 'nutrition_goals', ['goal_id'], ['id'], ondelete='CASCADE')
    
    # Drop the old unique constraint
    op.drop_constraint('uq_user_nutrient', 'user_nutrient_focus', type_='unique')
    
    # Create new unique constraint that includes goal_id
    op.create_unique_constraint('uq_user_nutrient_goal', 'user_nutrient_focus', ['user_id', 'nutrient_id', 'goal_id'])
    
    # Create index on goal_id for faster queries
    op.create_index('ix_user_nutrient_focus_goal_id', 'user_nutrient_focus', ['goal_id'])


def downgrade() -> None:
    # Drop the new index
    op.drop_index('ix_user_nutrient_focus_goal_id', table_name='user_nutrient_focus')
    
    # Drop the new unique constraint
    op.drop_constraint('uq_user_nutrient_goal', 'user_nutrient_focus', type_='unique')
    
    # Recreate the old unique constraint
    op.create_unique_constraint('uq_user_nutrient', 'user_nutrient_focus', ['user_id', 'nutrient_id'])
    
    # Drop the foreign key constraint
    op.drop_constraint('fk_user_nutrient_focus_goal_id', 'user_nutrient_focus', type_='foreignkey')
    
    # Drop the goal_id column
    op.drop_column('user_nutrient_focus', 'goal_id')
