"""Add user identities and login events for dual auth

Revision ID: 034_dual_auth
Revises: 033_password_reset_doctors
Create Date: 2025-01-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '034_dual_auth'
down_revision = '033_password_reset_doctors'
branch_labels = None
depends_on = None


def upgrade():
    # Create user_identities table
    op.create_table('user_identities',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('provider', sa.String(length=50), nullable=False),
    sa.Column('provider_subject', sa.String(length=255), nullable=True),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('email_verified', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('last_used_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('provider', 'provider_subject', name='uq_provider_subject')
    )
    op.create_index(op.f('ix_user_identities_id'), 'user_identities', ['id'], unique=False)

    # Create login_events table
    op.create_table('login_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('occurred_at', sa.DateTime(), nullable=False),
    sa.Column('method', sa.String(length=50), nullable=False),
    sa.Column('device_id', sa.String(length=255), nullable=True),
    sa.Column('device_model', sa.String(length=255), nullable=True),
    sa.Column('os_version', sa.String(length=100), nullable=True),
    sa.Column('app_version', sa.String(length=50), nullable=True),
    sa.Column('ip_address', sa.String(length=45), nullable=True),
    sa.Column('country', sa.String(length=100), nullable=True),
    sa.Column('region', sa.String(length=100), nullable=True),
    sa.Column('city', sa.String(length=100), nullable=True),
    sa.Column('user_agent', sa.Text(), nullable=True),
    sa.Column('success', sa.Boolean(), nullable=False),
    sa.Column('error_code', sa.String(length=100), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_login_events_id'), 'login_events', ['id'], unique=False)
    op.create_index('ix_login_events_user_occurred', 'login_events', ['user_id', 'occurred_at'], unique=False)

    # Add new columns to users table
    op.add_column('users', sa.Column('email_verified_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(), nullable=True))
    
    # Make hashed_password nullable for Google-only users
    op.alter_column('users', 'hashed_password', nullable=True)


def downgrade():
    # Remove new columns from users table
    op.alter_column('users', 'hashed_password', nullable=False)
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'email_verified_at')
    
    # Drop login_events table
    op.drop_index('ix_login_events_user_occurred', table_name='login_events')
    op.drop_index(op.f('ix_login_events_id'), table_name='login_events')
    op.drop_table('login_events')
    
    # Drop user_identities table
    op.drop_index(op.f('ix_user_identities_id'), table_name='user_identities')
    op.drop_table('user_identities')
