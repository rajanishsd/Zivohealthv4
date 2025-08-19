"""Add nutrition vitamins/minerals fields and medical images table

Revision ID: 008_add_nutrition_and_medical_images
Revises: 007_add_aggregation_status
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '008_add_nutrition_and_medical_images'
down_revision = '007_add_aggregation_status'
branch_labels = None
depends_on = None


def upgrade():
    # Add new fields to nutrition_raw_data table
    op.add_column('nutrition_raw_data', sa.Column('dish_name', sa.String(), nullable=True))
    op.add_column('nutrition_raw_data', sa.Column('dish_type', sa.String(), nullable=True))
    
    # Add vitamin fields
    op.add_column('nutrition_raw_data', sa.Column('vitamin_a_mcg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_raw_data', sa.Column('vitamin_c_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_raw_data', sa.Column('vitamin_d_mcg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_raw_data', sa.Column('vitamin_e_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_raw_data', sa.Column('vitamin_k_mcg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_raw_data', sa.Column('vitamin_b1_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_raw_data', sa.Column('vitamin_b2_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_raw_data', sa.Column('vitamin_b3_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_raw_data', sa.Column('vitamin_b6_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_raw_data', sa.Column('vitamin_b12_mcg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_raw_data', sa.Column('folate_mcg', sa.Float(), nullable=True, default=0.0))
    
    # Add mineral fields
    op.add_column('nutrition_raw_data', sa.Column('calcium_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_raw_data', sa.Column('iron_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_raw_data', sa.Column('magnesium_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_raw_data', sa.Column('phosphorus_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_raw_data', sa.Column('potassium_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_raw_data', sa.Column('zinc_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_raw_data', sa.Column('copper_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_raw_data', sa.Column('manganese_mg', sa.Float(), nullable=True, default=0.0))
    op.add_column('nutrition_raw_data', sa.Column('selenium_mcg', sa.Float(), nullable=True, default=0.0))
    
    # Add index for dish_type
    op.create_index('idx_nutrition_dish_type', 'nutrition_raw_data', ['dish_type', 'meal_date'])
    
    # Create medical_images table
    op.create_table('medical_images',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('image_type', sa.String(), nullable=False),
        sa.Column('body_part', sa.String(), nullable=True),
        sa.Column('image_path', sa.String(), nullable=False),
        sa.Column('original_filename', sa.String(), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('image_format', sa.String(), nullable=True),
        sa.Column('ai_summary', sa.Text(), nullable=True),
        sa.Column('ai_findings', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('exam_date', sa.Date(), nullable=True),
        sa.Column('ordering_physician', sa.String(), nullable=True),
        sa.Column('facility_name', sa.String(), nullable=True),
        sa.Column('exam_reason', sa.Text(), nullable=True),
        sa.Column('processing_status', sa.String(length=20), nullable=False, default='pending'),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for medical_images
    op.create_index('idx_medical_images_user_date', 'medical_images', ['user_id', 'exam_date'])
    op.create_index('idx_medical_images_type', 'medical_images', ['image_type', 'exam_date'])
    op.create_index('idx_medical_images_body_part', 'medical_images', ['body_part', 'exam_date'])
    op.create_index('idx_medical_images_status', 'medical_images', ['processing_status', 'user_id'])


def downgrade():
    # Drop medical_images table and indexes
    op.drop_index('idx_medical_images_status', table_name='medical_images')
    op.drop_index('idx_medical_images_body_part', table_name='medical_images')
    op.drop_index('idx_medical_images_type', table_name='medical_images')
    op.drop_index('idx_medical_images_user_date', table_name='medical_images')
    op.drop_table('medical_images')
    
    # Drop nutrition index
    op.drop_index('idx_nutrition_dish_type', table_name='nutrition_raw_data')
    
    # Remove mineral fields
    op.drop_column('nutrition_raw_data', 'selenium_mcg')
    op.drop_column('nutrition_raw_data', 'manganese_mg')
    op.drop_column('nutrition_raw_data', 'copper_mg')
    op.drop_column('nutrition_raw_data', 'zinc_mg')
    op.drop_column('nutrition_raw_data', 'potassium_mg')
    op.drop_column('nutrition_raw_data', 'phosphorus_mg')
    op.drop_column('nutrition_raw_data', 'magnesium_mg')
    op.drop_column('nutrition_raw_data', 'iron_mg')
    op.drop_column('nutrition_raw_data', 'calcium_mg')
    
    # Remove vitamin fields
    op.drop_column('nutrition_raw_data', 'folate_mcg')
    op.drop_column('nutrition_raw_data', 'vitamin_b12_mcg')
    op.drop_column('nutrition_raw_data', 'vitamin_b6_mg')
    op.drop_column('nutrition_raw_data', 'vitamin_b3_mg')
    op.drop_column('nutrition_raw_data', 'vitamin_b2_mg')
    op.drop_column('nutrition_raw_data', 'vitamin_b1_mg')
    op.drop_column('nutrition_raw_data', 'vitamin_k_mcg')
    op.drop_column('nutrition_raw_data', 'vitamin_e_mg')
    op.drop_column('nutrition_raw_data', 'vitamin_d_mcg')
    op.drop_column('nutrition_raw_data', 'vitamin_c_mg')
    op.drop_column('nutrition_raw_data', 'vitamin_a_mcg')
    
    # Remove dish fields
    op.drop_column('nutrition_raw_data', 'dish_type')
    op.drop_column('nutrition_raw_data', 'dish_name') 