"""add closed_date to feedback

Revision ID: 045_add_closed_date_to_feedback
Revises: 044_add_submitter_type_to_feedback
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '045_add_closed_date_to_feedback'
down_revision = '044_add_submitter_type_to_feedback'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add closed_date column to feedback_screenshots table
    op.add_column('feedback_screenshots', sa.Column('closed_date', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Remove closed_date column from feedback_screenshots table
    op.drop_column('feedback_screenshots', 'closed_date')
