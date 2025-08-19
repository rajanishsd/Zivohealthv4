"""change_aggregation_value_columns_to_varchar

Revision ID: 4e457822fdc5
Revises: b3e1cd69b494
Create Date: 2025-07-20 12:46:14.603037

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4e457822fdc5'
down_revision = 'b3e1cd69b494'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Change avg_value, min_value, max_value columns from double precision to varchar
    # in all four aggregation tables
    
    # lab_reports_daily table
    op.alter_column('lab_reports_daily', 'avg_value',
                    existing_type=sa.Double(),
                    type_=sa.String(length=100),
                    existing_nullable=True)
    op.alter_column('lab_reports_daily', 'min_value',
                    existing_type=sa.Double(),
                    type_=sa.String(length=100),
                    existing_nullable=True)
    op.alter_column('lab_reports_daily', 'max_value',
                    existing_type=sa.Double(),
                    type_=sa.String(length=100),
                    existing_nullable=True)
    
    # lab_reports_monthly table
    op.alter_column('lab_reports_monthly', 'avg_value',
                    existing_type=sa.Double(),
                    type_=sa.String(length=100),
                    existing_nullable=True)
    op.alter_column('lab_reports_monthly', 'min_value',
                    existing_type=sa.Double(),
                    type_=sa.String(length=100),
                    existing_nullable=True)
    op.alter_column('lab_reports_monthly', 'max_value',
                    existing_type=sa.Double(),
                    type_=sa.String(length=100),
                    existing_nullable=True)
    
    # lab_reports_quarterly table
    op.alter_column('lab_reports_quarterly', 'avg_value',
                    existing_type=sa.Double(),
                    type_=sa.String(length=100),
                    existing_nullable=True)
    op.alter_column('lab_reports_quarterly', 'min_value',
                    existing_type=sa.Double(),
                    type_=sa.String(length=100),
                    existing_nullable=True)
    op.alter_column('lab_reports_quarterly', 'max_value',
                    existing_type=sa.Double(),
                    type_=sa.String(length=100),
                    existing_nullable=True)
    
    # lab_reports_yearly table
    op.alter_column('lab_reports_yearly', 'avg_value',
                    existing_type=sa.Double(),
                    type_=sa.String(length=100),
                    existing_nullable=True)
    op.alter_column('lab_reports_yearly', 'min_value',
                    existing_type=sa.Double(),
                    type_=sa.String(length=100),
                    existing_nullable=True)
    op.alter_column('lab_reports_yearly', 'max_value',
                    existing_type=sa.Double(),
                    type_=sa.String(length=100),
                    existing_nullable=True)


def downgrade() -> None:
    # Revert back to double precision
    # lab_reports_daily table
    op.alter_column('lab_reports_daily', 'avg_value',
                    existing_type=sa.String(length=100),
                    type_=sa.Double(),
                    existing_nullable=True)
    op.alter_column('lab_reports_daily', 'min_value',
                    existing_type=sa.String(length=100),
                    type_=sa.Double(),
                    existing_nullable=True)
    op.alter_column('lab_reports_daily', 'max_value',
                    existing_type=sa.String(length=100),
                    type_=sa.Double(),
                    existing_nullable=True)
    
    # lab_reports_monthly table
    op.alter_column('lab_reports_monthly', 'avg_value',
                    existing_type=sa.String(length=100),
                    type_=sa.Double(),
                    existing_nullable=True)
    op.alter_column('lab_reports_monthly', 'min_value',
                    existing_type=sa.String(length=100),
                    type_=sa.Double(),
                    existing_nullable=True)
    op.alter_column('lab_reports_monthly', 'max_value',
                    existing_type=sa.String(length=100),
                    type_=sa.Double(),
                    existing_nullable=True)
    
    # lab_reports_quarterly table
    op.alter_column('lab_reports_quarterly', 'avg_value',
                    existing_type=sa.String(length=100),
                    type_=sa.Double(),
                    existing_nullable=True)
    op.alter_column('lab_reports_quarterly', 'min_value',
                    existing_type=sa.String(length=100),
                    type_=sa.Double(),
                    existing_nullable=True)
    op.alter_column('lab_reports_quarterly', 'max_value',
                    existing_type=sa.String(length=100),
                    type_=sa.Double(),
                    existing_nullable=True)
    
    # lab_reports_yearly table
    op.alter_column('lab_reports_yearly', 'avg_value',
                    existing_type=sa.String(length=100),
                    type_=sa.Double(),
                    existing_nullable=True)
    op.alter_column('lab_reports_yearly', 'min_value',
                    existing_type=sa.String(length=100),
                    type_=sa.Double(),
                    existing_nullable=True)
    op.alter_column('lab_reports_yearly', 'max_value',
                    existing_type=sa.String(length=100),
                    type_=sa.Double(),
                    existing_nullable=True) 