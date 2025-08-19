"""merge heads after adding doctor dob/contact

Revision ID: 2c6d1d805586
Revises: 008_add_doctor_dob_contact, 022, dbfc12478a54
Create Date: 2025-08-18 13:09:52.986154

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2c6d1d805586'
down_revision = ('008_add_doctor_dob_contact', '022', 'dbfc12478a54')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass 