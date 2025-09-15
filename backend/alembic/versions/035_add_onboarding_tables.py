"""add onboarding tables

Revision ID: 035_add_onboarding
Revises: 034_add_user_identities_and_login_events
Create Date: 2025-01-12
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '035_add_onboarding'
down_revision = 'd5bed3016eb0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_profiles',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('full_name', sa.String(length=255)),
        sa.Column('date_of_birth', sa.Date(), nullable=False),
        sa.Column('gender', sa.String(length=16), nullable=False),
        sa.Column('height_cm', sa.Integer()),
        sa.Column('weight_kg', sa.Integer()),
        sa.Column('body_type', sa.String(length=16)),
        sa.Column('activity_level', sa.String(length=24)),
        sa.Column('phone_number', sa.String(length=32), nullable=False),
        sa.Column('timezone', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'conditions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(length=64)),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('category', sa.String(length=64)),
        sa.UniqueConstraint('name'),
    )

    op.create_table(
        'allergens',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.UniqueConstraint('name'),
    )

    op.create_table(
        'user_conditions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('condition_id', sa.Integer(), sa.ForeignKey('conditions.id')),
        sa.Column('other_text', sa.String()),
        sa.Column('diagnosed_on', sa.Date()),
        sa.Column('severity', sa.String(length=16)),
        sa.Column('notes', sa.String()),
        sa.UniqueConstraint('user_id', 'condition_id', name='uq_user_condition'),
    )

    op.create_table(
        'user_allergies',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('allergen_id', sa.Integer(), sa.ForeignKey('allergens.id')),
        sa.Column('other_text', sa.String()),
        sa.Column('reaction', sa.String()),
        sa.Column('severity', sa.String(length=16)),
        sa.UniqueConstraint('user_id', 'allergen_id', name='uq_user_allergen'),
    )

    op.create_table(
        'user_lifestyle',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('smokes', sa.Boolean(), nullable=False),
        sa.Column('drinks_alcohol', sa.Boolean(), nullable=False),
        sa.Column('exercises_regularly', sa.Boolean(), nullable=False),
        sa.Column('exercise_type', sa.String(length=24)),
        sa.Column('exercise_frequency_per_week', sa.Integer()),
    )

    op.create_table(
        'user_notification_preferences',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('timezone', sa.String(length=64), nullable=False),
        sa.Column('window_start_local', sa.Time(), nullable=False),
        sa.Column('window_end_local', sa.Time(), nullable=False),
        sa.Column('email_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('sms_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('push_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
    )

    op.create_table(
        'user_consents',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('consent_type', sa.String(length=48), nullable=False),
        sa.Column('consented', sa.Boolean(), nullable=False),
        sa.Column('version', sa.String(length=32)),
        sa.Column('consented_at', sa.DateTime(), nullable=False),
        sa.Column('ip_address', sa.String(length=45)),
        sa.Column('user_agent', sa.String()),
    )

    op.create_table(
        'user_measurement_preferences',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('height_unit', sa.String(length=8), nullable=False, server_default='cm'),
        sa.Column('weight_unit', sa.String(length=8), nullable=False, server_default='kg'),
    )


def downgrade() -> None:
    op.drop_table('user_measurement_preferences')
    op.drop_table('user_consents')
    op.drop_table('user_notification_preferences')
    op.drop_table('user_lifestyle')
    op.drop_table('user_allergies')
    op.drop_table('user_conditions')
    op.drop_table('allergens')
    op.drop_table('conditions')
    op.drop_table('user_profiles')
