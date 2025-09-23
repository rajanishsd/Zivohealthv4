"""Add unified recurring reminders support

Revision ID: 039_recurring_unified
Revises: 038_add_onboarding_status
Create Date: 2025-01-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '039_recurring_unified'
down_revision = '038_add_onboarding_status'
branch_labels = None
depends_on = None


def upgrade():
    # Add basic fields first
    op.add_column('reminders', sa.Column('title', sa.String, nullable=True))
    op.add_column('reminders', sa.Column('message', sa.String, nullable=True))
    
    # Add recurrence fields to existing reminders table for unified approach
    op.add_column('reminders', sa.Column('recurrence_pattern', postgresql.JSONB, nullable=True))
    op.add_column('reminders', sa.Column('is_recurring', sa.Boolean, nullable=False, server_default=sa.text('FALSE')))
    op.add_column('reminders', sa.Column('parent_reminder_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('reminders', sa.Column('occurrence_number', sa.Integer, nullable=True))
    op.add_column('reminders', sa.Column('is_generated', sa.Boolean, nullable=False, server_default=sa.text('FALSE')))
    op.add_column('reminders', sa.Column('start_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('reminders', sa.Column('end_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('reminders', sa.Column('max_occurrences', sa.Integer, nullable=True))
    op.add_column('reminders', sa.Column('timezone', sa.String, nullable=True))
    op.add_column('reminders', sa.Column('last_occurrence', sa.DateTime(timezone=True), nullable=True))
    op.add_column('reminders', sa.Column('next_occurrence', sa.DateTime(timezone=True), nullable=True))
    op.add_column('reminders', sa.Column('occurrence_count', sa.Integer, nullable=False, server_default=sa.text('0')))
    op.add_column('reminders', sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.text('TRUE')))
    
    # Create indexes for performance
    op.create_index('ix_reminders_recurring_active', 'reminders', ['is_recurring', 'is_active'])
    op.create_index('ix_reminders_next_occurrence', 'reminders', ['next_occurrence'])
    op.create_index('ix_reminders_parent_id', 'reminders', ['parent_reminder_id'])
    
    # Create foreign key for parent_reminder_id (self-referencing)
    op.create_foreign_key(
        'fk_reminders_parent_reminder_id',
        'reminders', 'reminders',
        ['parent_reminder_id'], ['id']
    )


def downgrade():
    # Drop foreign key
    op.drop_constraint('fk_reminders_parent_reminder_id', 'reminders', type_='foreignkey')
    
    # Drop indexes
    op.drop_index('ix_reminders_parent_id', 'reminders')
    op.drop_index('ix_reminders_next_occurrence', 'reminders')
    op.drop_index('ix_reminders_recurring_active', 'reminders')
    
    # Drop columns
    op.drop_column('reminders', 'is_active')
    op.drop_column('reminders', 'occurrence_count')
    op.drop_column('reminders', 'next_occurrence')
    op.drop_column('reminders', 'last_occurrence')
    op.drop_column('reminders', 'timezone')
    op.drop_column('reminders', 'max_occurrences')
    op.drop_column('reminders', 'end_date')
    op.drop_column('reminders', 'start_date')
    op.drop_column('reminders', 'is_generated')
    op.drop_column('reminders', 'occurrence_number')
    op.drop_column('reminders', 'parent_reminder_id')
    op.drop_column('reminders', 'is_recurring')
    op.drop_column('reminders', 'recurrence_pattern')
    op.drop_column('reminders', 'message')
    op.drop_column('reminders', 'title')
