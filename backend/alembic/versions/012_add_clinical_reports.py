"""Add clinical reports table

Revision ID: 012_add_clinical_reports
Revises: 011_add_nutrition_daily_aggregates
Create Date: 2025-01-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '012_add_clinical_reports'
down_revision = '011_add_vitals_unique_constraint'
branch_labels = None
depends_on = None


def upgrade():
    # Create clinical_reports table
    op.create_table('clinical_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('chat_session_id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=True),
        sa.Column('user_question', sa.Text(), nullable=False),
        sa.Column('ai_response', sa.Text(), nullable=False),
        sa.Column('comprehensive_context', sa.Text(), nullable=False),
        sa.Column('data_sources_summary', sa.Text(), nullable=True),
        sa.Column('vitals_data', sa.Text(), nullable=True),
        sa.Column('nutrition_data', sa.Text(), nullable=True),
        sa.Column('prescription_data', sa.Text(), nullable=True),
        sa.Column('lab_data', sa.Text(), nullable=True),
        sa.Column('pharmacy_data', sa.Text(), nullable=True),
        sa.Column('agent_requirements', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_clinical_reports_id'), 'clinical_reports', ['id'], unique=False)
    op.create_index('ix_clinical_reports_user_id', 'clinical_reports', ['user_id'], unique=False)
    op.create_index('ix_clinical_reports_chat_session_id', 'clinical_reports', ['chat_session_id'], unique=False)
    op.create_index('ix_clinical_reports_created_at', 'clinical_reports', ['created_at'], unique=False)

    # Add clinical_report_id column to consultation_requests table
    op.add_column('consultation_requests', sa.Column('clinical_report_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_consultation_requests_clinical_report_id', 'consultation_requests', 'clinical_reports', ['clinical_report_id'], ['id'])
    op.create_index('ix_consultation_requests_clinical_report_id', 'consultation_requests', ['clinical_report_id'], unique=False)


def downgrade():
    # Remove foreign key and column from consultation_requests
    op.drop_index('ix_consultation_requests_clinical_report_id', table_name='consultation_requests')
    op.drop_constraint('fk_consultation_requests_clinical_report_id', 'consultation_requests', type_='foreignkey')
    op.drop_column('consultation_requests', 'clinical_report_id')
    
    # Drop clinical_reports table
    op.drop_index('ix_clinical_reports_created_at', table_name='clinical_reports')
    op.drop_index('ix_clinical_reports_chat_session_id', table_name='clinical_reports')
    op.drop_index('ix_clinical_reports_user_id', table_name='clinical_reports')
    op.drop_index(op.f('ix_clinical_reports_id'), table_name='clinical_reports')
    op.drop_table('clinical_reports') 