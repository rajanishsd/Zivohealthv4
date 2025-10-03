"""043_add_app_identifier_column

Revision ID: 9c3732733048
Revises: 9edfb7296591
Create Date: 2025-10-01 14:48:15.815302

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c3732733048'
down_revision = '9edfb7296591'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add the missing app_identifier column to feedback_screenshots table
    op.add_column('feedback_screenshots', sa.Column('app_identifier', sa.String(length=200), nullable=True))


def downgrade() -> None:
    # Remove the app_identifier column
    op.drop_column('feedback_screenshots', 'app_identifier') 