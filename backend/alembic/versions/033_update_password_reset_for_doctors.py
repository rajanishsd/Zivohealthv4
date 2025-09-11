"""Update password reset tokens to support both users and doctors

Revision ID: 033
Revises: 032
Create Date: 2025-01-10 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '033_password_reset_doctors'
down_revision = '032_add_password_reset'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to support both users and doctors
    op.add_column('password_reset_tokens', sa.Column('doctor_id', sa.Integer(), nullable=True))
    op.add_column('password_reset_tokens', sa.Column('user_type', sa.String(10), nullable=False, server_default='user'))
    
    # Add foreign key constraint for doctor_id
    op.create_foreign_key('fk_password_reset_tokens_doctor_id', 'password_reset_tokens', 'doctors', ['doctor_id'], ['id'], ondelete='CASCADE')
    
    # Make user_id nullable since we now support doctors
    op.alter_column('password_reset_tokens', 'user_id', nullable=True)
    
    # Add indexes for the new columns
    op.create_index('ix_password_reset_tokens_doctor_id', 'password_reset_tokens', ['doctor_id'])
    op.create_index('ix_password_reset_tokens_user_type', 'password_reset_tokens', ['user_type'])
    
    # Add check constraint to ensure either user_id or doctor_id is set, but not both
    op.create_check_constraint(
        'ck_password_reset_tokens_user_or_doctor',
        'password_reset_tokens',
        '(user_id IS NOT NULL AND doctor_id IS NULL) OR (user_id IS NULL AND doctor_id IS NOT NULL)'
    )


def downgrade():
    # Remove check constraint
    op.drop_constraint('ck_password_reset_tokens_user_or_doctor', 'password_reset_tokens', type_='check')
    
    # Remove indexes
    op.drop_index('ix_password_reset_tokens_user_type', table_name='password_reset_tokens')
    op.drop_index('ix_password_reset_tokens_doctor_id', table_name='password_reset_tokens')
    
    # Make user_id not nullable again
    op.alter_column('password_reset_tokens', 'user_id', nullable=False)
    
    # Remove foreign key constraint
    op.drop_constraint('fk_password_reset_tokens_doctor_id', 'password_reset_tokens', type_='foreignkey')
    
    # Remove new columns
    op.drop_column('password_reset_tokens', 'user_type')
    op.drop_column('password_reset_tokens', 'doctor_id')
