"""update_pharmacybill_filepath

Revision ID: 019_update_pharmacybill_filepath
Revises: 90d1fbcd5617
Create Date: 2025-01-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '019_update_pharmacybill_filepath'
down_revision = '90d1fbcd5617'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Update pharmacy_bills table to rename extracted_from_document_id to pharmacybill_filepath
    # and change type from integer to varchar(500)
    
    # First drop the existing column
    op.drop_column('pharmacy_bills', 'extracted_from_document_id')
    
    # Add the new column with the correct name and type
    op.add_column('pharmacy_bills', sa.Column('pharmacybill_filepath', sa.String(500), nullable=True))


def downgrade() -> None:
    # Revert the changes
    # Drop the new column
    op.drop_column('pharmacy_bills', 'pharmacybill_filepath')
    
    # Add back the original column
    op.add_column('pharmacy_bills', sa.Column('extracted_from_document_id', sa.Integer(), nullable=True))