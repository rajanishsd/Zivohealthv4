"""
Replace test_name with loinc_code in lab_report_categorized primary key
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'replace_testname_with_loinccode'
down_revision = 'b3e1cd69b494'  # Latest merge migration
branch_labels = None
depends_on = None

def upgrade():
    # 1. Ensure all records have a non-null loinc_code (set to 'UNKNOWN' if missing)
    op.execute("""
        UPDATE lab_report_categorized
        SET loinc_code = 'UNKNOWN'
        WHERE loinc_code IS NULL
    """)

    # 2. Drop the old primary key constraint
    op.drop_constraint(
        constraint_name='lab_report_categorized_pkey',
        table_name='lab_report_categorized',
        type_='primary'
    )

    # 3. Create the new primary key constraint
    op.create_primary_key(
        constraint_name='lab_report_categorized_pkey',
        table_name='lab_report_categorized',
        columns=['user_id', 'loinc_code', 'test_value', 'test_date']
    )

def downgrade():
    # 1. Drop the new primary key constraint
    op.drop_constraint(
        constraint_name='lab_report_categorized_pkey',
        table_name='lab_report_categorized',
        type_='primary'
    )

    # 2. Recreate the old primary key constraint
    op.create_primary_key(
        constraint_name='lab_report_categorized_pkey',
        table_name='lab_report_categorized',
        columns=['user_id', 'test_name', 'test_value', 'test_date']
    ) 