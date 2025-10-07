"""drop users.timezone_id

Revision ID: 053
Revises: 052
Create Date: 2025-10-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '053'
down_revision = '052'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop FK if exists, then drop column
    conn = op.get_bind()
    insp = sa.inspect(conn)
    fks = [fk['name'] for fk in insp.get_foreign_keys('users') if fk.get('referred_table') == 'timezone_dictionary']
    for fk_name in fks:
        try:
            op.drop_constraint(fk_name, 'users', type_='foreignkey')
        except Exception:
            pass
    with op.batch_alter_table('users') as batch_op:
        if 'timezone_id' in [c['name'] for c in insp.get_columns('users')]:
            batch_op.drop_column('timezone_id')


def downgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('timezone_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_users_timezone', 'timezone_dictionary', ['timezone_id'], ['id'])
