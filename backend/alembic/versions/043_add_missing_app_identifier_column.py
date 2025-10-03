"""add_missing_app_identifier_column

Revision ID: 043_add_app_identifier
Revises: d830f765b5ee
Create Date: 2025-10-01 14:46:30.280953

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '043_add_app_identifier'
down_revision = 'd830f765b5ee'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add the missing app_identifier column to feedback_screenshots table
    op.add_column('feedback_screenshots', sa.Column('app_identifier', sa.String(length=200), nullable=True))


def downgrade() -> None:
    # Remove the app_identifier column
    op.drop_column('feedback_screenshots', 'app_identifier') 