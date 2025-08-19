"""add vitamins and minerals to aggregates

Revision ID: 009_add_vitamins_minerals_to_aggregates
Revises: 008_add_nutrition_and_medical_images
Create Date: 2025-06-21 17:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009_add_vitamins_minerals_to_aggregates'
down_revision: Union[str, None] = '008_add_nutrition_and_medical_images'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add vitamin fields to nutrition_daily_aggregates
    op.add_column('nutrition_daily_aggregates', sa.Column('total_vitamin_a_mcg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_daily_aggregates', sa.Column('total_vitamin_c_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_daily_aggregates', sa.Column('total_vitamin_d_mcg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_daily_aggregates', sa.Column('total_vitamin_e_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_daily_aggregates', sa.Column('total_vitamin_k_mcg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_daily_aggregates', sa.Column('total_vitamin_b1_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_daily_aggregates', sa.Column('total_vitamin_b2_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_daily_aggregates', sa.Column('total_vitamin_b3_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_daily_aggregates', sa.Column('total_vitamin_b6_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_daily_aggregates', sa.Column('total_vitamin_b12_mcg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_daily_aggregates', sa.Column('total_folate_mcg', sa.Float(), nullable=True, default=0.0))
    
    # Add mineral fields to nutrition_daily_aggregates
    op.add_column('nutrition_daily_aggregates', sa.Column('total_calcium_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_daily_aggregates', sa.Column('total_iron_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_daily_aggregates', sa.Column('total_magnesium_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_daily_aggregates', sa.Column('total_phosphorus_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_daily_aggregates', sa.Column('total_potassium_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_daily_aggregates', sa.Column('total_zinc_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_daily_aggregates', sa.Column('total_copper_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_daily_aggregates', sa.Column('total_manganese_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_daily_aggregates', sa.Column('total_selenium_mcg', sa.Float(), nullable=True, default=0.0))
    
    # Add vitamin fields to nutrition_weekly_aggregates
    op.add_column('nutrition_weekly_aggregates', sa.Column('avg_daily_vitamin_a_mcg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_weekly_aggregates', sa.Column('avg_daily_vitamin_c_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_weekly_aggregates', sa.Column('avg_daily_vitamin_d_mcg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_weekly_aggregates', sa.Column('avg_daily_vitamin_e_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_weekly_aggregates', sa.Column('avg_daily_vitamin_k_mcg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_weekly_aggregates', sa.Column('avg_daily_vitamin_b1_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_weekly_aggregates', sa.Column('avg_daily_vitamin_b2_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_weekly_aggregates', sa.Column('avg_daily_vitamin_b3_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_weekly_aggregates', sa.Column('avg_daily_vitamin_b6_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_weekly_aggregates', sa.Column('avg_daily_vitamin_b12_mcg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_weekly_aggregates', sa.Column('avg_daily_folate_mcg', sa.Float(), nullable=True, default=0.0))
    
    # Add mineral fields to nutrition_weekly_aggregates
    op.add_column('nutrition_weekly_aggregates', sa.Column('avg_daily_calcium_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_weekly_aggregates', sa.Column('avg_daily_iron_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_weekly_aggregates', sa.Column('avg_daily_magnesium_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_weekly_aggregates', sa.Column('avg_daily_phosphorus_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_weekly_aggregates', sa.Column('avg_daily_potassium_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_weekly_aggregates', sa.Column('avg_daily_zinc_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_weekly_aggregates', sa.Column('avg_daily_copper_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_weekly_aggregates', sa.Column('avg_daily_manganese_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_weekly_aggregates', sa.Column('avg_daily_selenium_mcg', sa.Float(), nullable=True, default=0.0))
    
    # Add vitamin fields to nutrition_monthly_aggregates
    op.add_column('nutrition_monthly_aggregates', sa.Column('avg_daily_vitamin_a_mcg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_monthly_aggregates', sa.Column('avg_daily_vitamin_c_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_monthly_aggregates', sa.Column('avg_daily_vitamin_d_mcg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_monthly_aggregates', sa.Column('avg_daily_vitamin_e_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_monthly_aggregates', sa.Column('avg_daily_vitamin_k_mcg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_monthly_aggregates', sa.Column('avg_daily_vitamin_b1_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_monthly_aggregates', sa.Column('avg_daily_vitamin_b2_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_monthly_aggregates', sa.Column('avg_daily_vitamin_b3_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_monthly_aggregates', sa.Column('avg_daily_vitamin_b6_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_monthly_aggregates', sa.Column('avg_daily_vitamin_b12_mcg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_monthly_aggregates', sa.Column('avg_daily_folate_mcg', sa.Float(), nullable=True, default=0.0))
    
    # Add mineral fields to nutrition_monthly_aggregates
    op.add_column('nutrition_monthly_aggregates', sa.Column('avg_daily_calcium_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_monthly_aggregates', sa.Column('avg_daily_iron_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_monthly_aggregates', sa.Column('avg_daily_magnesium_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_monthly_aggregates', sa.Column('avg_daily_phosphorus_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_monthly_aggregates', sa.Column('avg_daily_potassium_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_monthly_aggregates', sa.Column('avg_daily_zinc_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_monthly_aggregates', sa.Column('avg_daily_copper_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_monthly_aggregates', sa.Column('avg_daily_manganese_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_monthly_aggregates', sa.Column('avg_daily_selenium_mcg', sa.Float(), nullable=True, default=0.0))


def downgrade() -> None:
    # Remove vitamin and mineral fields from nutrition_monthly_aggregates
    op.drop_column('nutrition_monthly_aggregates', 'avg_daily_selenium_mcg')
    op.drop_column('nutrition_monthly_aggregates', 'avg_daily_manganese_mg')
    op.drop_column('nutrition_monthly_aggregates', 'avg_daily_copper_mg')
    op.drop_column('nutrition_monthly_aggregates', 'avg_daily_zinc_mg')
    op.drop_column('nutrition_monthly_aggregates', 'avg_daily_potassium_mg')
    op.drop_column('nutrition_monthly_aggregates', 'avg_daily_phosphorus_mg')
    op.drop_column('nutrition_monthly_aggregates', 'avg_daily_magnesium_mg')
    op.drop_column('nutrition_monthly_aggregates', 'avg_daily_iron_mg')
    op.drop_column('nutrition_monthly_aggregates', 'avg_daily_calcium_mg')
    op.drop_column('nutrition_monthly_aggregates', 'avg_daily_folate_mcg')
    op.drop_column('nutrition_monthly_aggregates', 'avg_daily_vitamin_b12_mcg')
    op.drop_column('nutrition_monthly_aggregates', 'avg_daily_vitamin_b6_mg')
    op.drop_column('nutrition_monthly_aggregates', 'avg_daily_vitamin_b3_mg')
    op.drop_column('nutrition_monthly_aggregates', 'avg_daily_vitamin_b2_mg')
    op.drop_column('nutrition_monthly_aggregates', 'avg_daily_vitamin_b1_mg')
    op.drop_column('nutrition_monthly_aggregates', 'avg_daily_vitamin_k_mcg')
    op.drop_column('nutrition_monthly_aggregates', 'avg_daily_vitamin_e_mg')
    op.drop_column('nutrition_monthly_aggregates', 'avg_daily_vitamin_d_mcg')
    op.drop_column('nutrition_monthly_aggregates', 'avg_daily_vitamin_c_mg')
    op.drop_column('nutrition_monthly_aggregates', 'avg_daily_vitamin_a_mcg')
    
    # Remove vitamin and mineral fields from nutrition_weekly_aggregates
    op.drop_column('nutrition_weekly_aggregates', 'avg_daily_selenium_mcg')
    op.drop_column('nutrition_weekly_aggregates', 'avg_daily_manganese_mg')
    op.drop_column('nutrition_weekly_aggregates', 'avg_daily_copper_mg')
    op.drop_column('nutrition_weekly_aggregates', 'avg_daily_zinc_mg')
    op.drop_column('nutrition_weekly_aggregates', 'avg_daily_potassium_mg')
    op.drop_column('nutrition_weekly_aggregates', 'avg_daily_phosphorus_mg')
    op.drop_column('nutrition_weekly_aggregates', 'avg_daily_magnesium_mg')
    op.drop_column('nutrition_weekly_aggregates', 'avg_daily_iron_mg')
    op.drop_column('nutrition_weekly_aggregates', 'avg_daily_calcium_mg')
    op.drop_column('nutrition_weekly_aggregates', 'avg_daily_folate_mcg')
    op.drop_column('nutrition_weekly_aggregates', 'avg_daily_vitamin_b12_mcg')
    op.drop_column('nutrition_weekly_aggregates', 'avg_daily_vitamin_b6_mg')
    op.drop_column('nutrition_weekly_aggregates', 'avg_daily_vitamin_b3_mg')
    op.drop_column('nutrition_weekly_aggregates', 'avg_daily_vitamin_b2_mg')
    op.drop_column('nutrition_weekly_aggregates', 'avg_daily_vitamin_b1_mg')
    op.drop_column('nutrition_weekly_aggregates', 'avg_daily_vitamin_k_mcg')
    op.drop_column('nutrition_weekly_aggregates', 'avg_daily_vitamin_e_mg')
    op.drop_column('nutrition_weekly_aggregates', 'avg_daily_vitamin_d_mcg')
    op.drop_column('nutrition_weekly_aggregates', 'avg_daily_vitamin_c_mg')
    op.drop_column('nutrition_weekly_aggregates', 'avg_daily_vitamin_a_mcg')
    
    # Remove vitamin and mineral fields from nutrition_daily_aggregates
    op.drop_column('nutrition_daily_aggregates', 'total_selenium_mcg')
    op.drop_column('nutrition_daily_aggregates', 'total_manganese_mg')
    op.drop_column('nutrition_daily_aggregates', 'total_copper_mg')
    op.drop_column('nutrition_daily_aggregates', 'total_zinc_mg')
    op.drop_column('nutrition_daily_aggregates', 'total_potassium_mg')
    op.drop_column('nutrition_daily_aggregates', 'total_phosphorus_mg')
    op.drop_column('nutrition_daily_aggregates', 'total_magnesium_mg')
    op.drop_column('nutrition_daily_aggregates', 'total_iron_mg')
    op.drop_column('nutrition_daily_aggregates', 'total_calcium_mg')
    op.drop_column('nutrition_daily_aggregates', 'total_folate_mcg')
    op.drop_column('nutrition_daily_aggregates', 'total_vitamin_b12_mcg')
    op.drop_column('nutrition_daily_aggregates', 'total_vitamin_b6_mg')
    op.drop_column('nutrition_daily_aggregates', 'total_vitamin_b3_mg')
    op.drop_column('nutrition_daily_aggregates', 'total_vitamin_b2_mg')
    op.drop_column('nutrition_daily_aggregates', 'total_vitamin_b1_mg')
    op.drop_column('nutrition_daily_aggregates', 'total_vitamin_k_mcg')
    op.drop_column('nutrition_daily_aggregates', 'total_vitamin_e_mg')
    op.drop_column('nutrition_daily_aggregates', 'total_vitamin_d_mcg')
    op.drop_column('nutrition_daily_aggregates', 'total_vitamin_c_mg')
    op.drop_column('nutrition_daily_aggregates', 'total_vitamin_a_mcg') 