"""add_source_column_to_vitals_mappings

Revision ID: 5b6ec0991a87
Revises: 500ad6b623e7
Create Date: 2025-07-13 17:16:33.279625

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5b6ec0991a87'
down_revision = '013_loincagg'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add source column to vitals_mappings table
    op.add_column('vitals_mappings', sa.Column('loinc_source', sa.String(255), nullable=True))


def downgrade() -> None:
    # Remove source column from vitals_mappings table
    op.drop_column('vitals_mappings', 'loinc_source') 