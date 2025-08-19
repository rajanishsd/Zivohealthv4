"""Add missing tables doctors consultation_requests and prescriptions

Revision ID: add_missing_tables
Revises: 3cb2951cc404
Create Date: 2025-06-02 23:10:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_missing_tables'
down_revision = '3cb2951cc404'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create doctors table
    op.create_table('doctors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=False),
        sa.Column('license_number', sa.String(), nullable=False),
        sa.Column('specialization', sa.String(), nullable=False),
        sa.Column('years_experience', sa.Integer(), nullable=False),
        sa.Column('rating', sa.Float(), nullable=True),
        sa.Column('total_consultations', sa.Integer(), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('is_available', sa.Boolean(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('license_number')
    )
    op.create_index('ix_doctors_email', 'doctors', ['email'], unique=True)
    op.create_index('ix_doctors_id', 'doctors', ['id'], unique=False)

    # Create consultation_requests table
    op.create_table('consultation_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('doctor_id', sa.Integer(), nullable=False),
        sa.Column('chat_session_id', sa.Integer(), nullable=True),
        sa.Column('context', sa.Text(), nullable=False),
        sa.Column('user_question', sa.Text(), nullable=False),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('urgency_level', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('doctor_notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['doctor_id'], ['doctors.id'], ),
        sa.ForeignKeyConstraint(['chat_session_id'], ['chat_sessions.id'], )
    )
    op.create_index('ix_consultation_requests_id', 'consultation_requests', ['id'], unique=False)

    # Create prescriptions table with string IDs for now (matching existing chat_sessions)
    op.create_table('prescriptions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('consultation_request_id', sa.Integer(), nullable=True),
        sa.Column('medication_name', sa.String(length=255), nullable=False),
        sa.Column('dosage', sa.String(length=100), nullable=True),
        sa.Column('frequency', sa.String(length=100), nullable=True),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('prescribed_by', sa.String(length=255), nullable=False),
        sa.Column('prescribed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['consultation_request_id'], ['consultation_requests.id'], ),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Update existing chat_sessions table
    op.add_column('chat_sessions', sa.Column('last_message_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True))
    op.add_column('chat_sessions', sa.Column('message_count', sa.Integer(), nullable=True))
    op.add_column('chat_sessions', sa.Column('has_verification', sa.Boolean(), nullable=True))
    op.add_column('chat_sessions', sa.Column('has_prescriptions', sa.Boolean(), nullable=True))
    op.add_column('chat_sessions', sa.Column('is_active', sa.Boolean(), nullable=True))

    # Update existing chat_messages table
    op.add_column('chat_messages', sa.Column('tokens_used', sa.Integer(), nullable=True))
    op.add_column('chat_messages', sa.Column('response_time_ms', sa.Integer(), nullable=True))


def downgrade() -> None:
    # Drop columns from existing tables
    op.drop_column('chat_messages', 'response_time_ms')
    op.drop_column('chat_messages', 'tokens_used')
    op.drop_column('chat_sessions', 'is_active')
    op.drop_column('chat_sessions', 'has_prescriptions')
    op.drop_column('chat_sessions', 'has_verification')
    op.drop_column('chat_sessions', 'message_count')
    op.drop_column('chat_sessions', 'last_message_at')
    
    # Drop new tables
    op.drop_table('prescriptions')
    op.drop_index('ix_consultation_requests_id', table_name='consultation_requests')
    op.drop_table('consultation_requests')
    op.drop_index('ix_doctors_id', table_name='doctors')
    op.drop_index('ix_doctors_email', table_name='doctors')
    op.drop_table('doctors') 