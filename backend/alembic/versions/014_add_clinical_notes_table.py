"""add clinical_notes table

Revision ID: 014
Revises: 013_loincagg
Create Date: 2024-01-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '014'
down_revision = '013_loincagg'
branch_labels = None
depends_on = None


def upgrade():
    # Create clinical_notes table
    op.create_table('clinical_notes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('chat_sessions.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        
        # Core clinical information
        sa.Column('diagnosis', sa.Text(), nullable=True),
        sa.Column('symptoms_presented', sa.Text(), nullable=True),
        sa.Column('doctor_observations', sa.Text(), nullable=True),
        sa.Column('clinical_findings', sa.Text(), nullable=True),
        
        # Treatment and care information
        sa.Column('treatment_plan', sa.Text(), nullable=True),
        sa.Column('follow_up_recommendations', sa.Text(), nullable=True),
        sa.Column('vital_signs_mentioned', sa.Text(), nullable=True),
        sa.Column('medical_history_noted', sa.Text(), nullable=True),
        
        # Additional clinical context
        sa.Column('visit_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('clinic_or_hospital', sa.String(255), nullable=True),
        sa.Column('attending_physician', sa.String(255), nullable=True),
        sa.Column('specialty', sa.String(100), nullable=True),
        
        # Document metadata
        sa.Column('document_type', sa.String(100), nullable=True),
        sa.Column('document_image_link', sa.String(500), nullable=True),
        
        # Audit fields
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade():
    op.drop_table('clinical_notes') 