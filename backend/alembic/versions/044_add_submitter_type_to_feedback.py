"""044_add_submitter_type_to_feedback

Revision ID: 044_add_submitter_type_to_feedback
Revises: 043_add_missing_app_identifier_column
Create Date: 2025-10-01 14:58:44.113720

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '044_add_submitter_type_to_feedback'
down_revision = '043_add_app_identifier'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add submitter_type column to feedback_screenshots table
    op.add_column('feedback_screenshots', sa.Column('submitter_type', sa.String(length=20), nullable=True))
    
    # Update existing records to set submitter_type based on current logic
    # This is a temporary fix for existing data
    op.execute("""
        UPDATE feedback_screenshots 
        SET submitter_type = CASE 
            WHEN user_id IN (SELECT id FROM doctors) THEN 'doctor'
            WHEN user_id IN (SELECT id FROM users) THEN 'user'
            ELSE 'unknown'
        END
        WHERE submitter_type IS NULL
    """)


def downgrade() -> None:
    # Remove the submitter_type column
    op.drop_column('feedback_screenshots', 'submitter_type')
