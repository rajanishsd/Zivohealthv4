"""Add date_of_birth and contact_number to doctors

Revision ID: 008_add_doctor_dob_contact
Revises: 007_add_aggregation_status
Create Date: 2025-08-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '008_add_doctor_dob_contact'
down_revision = '007_add_aggregation_status'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('doctors', sa.Column('date_of_birth', sa.Date(), nullable=True))
    op.add_column('doctors', sa.Column('contact_number', sa.String(), nullable=True))


def downgrade():
    op.drop_column('doctors', 'contact_number')
    op.drop_column('doctors', 'date_of_birth')


