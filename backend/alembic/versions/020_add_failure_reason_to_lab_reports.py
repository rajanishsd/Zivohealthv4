"""Add failure_reason column to lab_reports table

Revision ID: 021
Revises: 020
Create Date: 2025-01-27 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '021'
down_revision = '020'
branch_labels = None
depends_on = None


def upgrade():
    """Add failure_reason column to lab_reports table"""
    op.add_column('lab_reports', sa.Column('failure_reason', sa.String(255), nullable=True))


def downgrade():
    """Remove failure_reason column from lab_reports table"""
    op.drop_column('lab_reports', 'failure_reason')