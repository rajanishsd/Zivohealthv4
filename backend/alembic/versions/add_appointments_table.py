"""Add appointments table

Revision ID: add_appointments_table
Revises: 
Create Date: 2024-01-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_appointments_table'
down_revision = None
depends_on = None

def upgrade() -> None:
    # Create appointments table
    op.create_table(
        'appointments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('doctor_id', sa.Integer(), nullable=False),
        sa.Column('consultation_request_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('appointment_date', sa.DateTime(), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('appointment_type', sa.String(), nullable=True),
        sa.Column('patient_notes', sa.Text(), nullable=True),
        sa.Column('doctor_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['doctor_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['consultation_request_id'], ['consultation_requests.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_appointments_id'), 'appointments', ['id'], unique=False)

def downgrade() -> None:
    # Drop appointments table
    op.drop_index(op.f('ix_appointments_id'), table_name='appointments')
    op.drop_table('appointments') 