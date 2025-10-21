"""drop legacy columns from mental_health_entries

Revision ID: 062
Revises: 061
Create Date: 2025-10-14 13:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '062'
down_revision = '061'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop legacy columns now that normalization is in place
    with op.batch_alter_table('mental_health_entries') as batch_op:
        for col in ['feelings_json', 'impacts_json', 'pleasantness_label', 'pleasantness_score', 'entry_type']:
            try:
                batch_op.drop_column(col)
            except Exception:
                # Column may already be absent in some environments
                pass


def downgrade() -> None:
    # Recreate legacy columns (types match original definitions)
    with op.batch_alter_table('mental_health_entries') as batch_op:
        batch_op.add_column(sa.Column('entry_type', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('pleasantness_score', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('pleasantness_label', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('feelings_json', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('impacts_json', sa.Text(), nullable=True))


