"""add country_code_id to user_profiles

Revision ID: 055
Revises: 054_country_code_dictionary
Create Date: 2025-10-07 14:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '055'
down_revision = '054'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('user_profiles', sa.Column('country_code_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_user_profiles_country_code',
        'user_profiles',
        'country_code_dictionary',
        ['country_code_id'],
        ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_user_profiles_country_code', 'user_profiles', type_='foreignkey')
    op.drop_column('user_profiles', 'country_code_id')


