"""add country code dictionary

Revision ID: 054
Revises: 053_drop_users_timezone_id
Create Date: 2025-10-07 13:50:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime
from pathlib import Path
import json


# revision identifiers, used by Alembic.
revision = '054'
down_revision = '053'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'country_code_dictionary',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('country_name', sa.String(length=64), nullable=False),
        sa.Column('iso2', sa.String(length=2), nullable=False),
        sa.Column('dial_code', sa.String(length=8), nullable=False),
        sa.Column('min_digits', sa.Integer(), nullable=False),
        sa.Column('max_digits', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_unique_constraint('uq_country_iso2', 'country_code_dictionary', ['iso2'])
    op.create_unique_constraint('uq_country_dial_code_iso2', 'country_code_dictionary', ['dial_code', 'iso2'])

    # Seed from JSON if available; fallback to a small seed
    data_file_candidates = [
        # typical project path
        Path(__file__).resolve().parents[3] / "backend" / "data" / "country_codes.json",
        Path(__file__).resolve().parents[2] / "data" / "country_codes.json",
    ]

    seed_records = []
    for p in data_file_candidates:
        if p.exists():
            try:
                with p.open("r", encoding="utf-8") as f:
                    payload = json.load(f)
                # Expect list of objects with keys: country_name, iso2, dial_code, min_digits, max_digits, is_active(optional)
                if isinstance(payload, list):
                    seed_records = payload
                    break
            except Exception:
                pass

    if not seed_records:
        seed_records = [
            {"country_name": "United States", "iso2": "US", "dial_code": "+1", "min_digits": 10, "max_digits": 10},
            {"country_name": "United Kingdom", "iso2": "GB", "dial_code": "+44", "min_digits": 10, "max_digits": 10},
            {"country_name": "India", "iso2": "IN", "dial_code": "+91", "min_digits": 10, "max_digits": 10},
        ]

    now = datetime.utcnow()
    conn = op.get_bind()
    for rec in seed_records:
        conn.execute(
            sa.text(
                """
                INSERT INTO country_code_dictionary (country_name, iso2, dial_code, min_digits, max_digits, is_active, created_at, updated_at)
                VALUES (:country_name, :iso2, :dial_code, :min_digits, :max_digits, :is_active, :created_at, :updated_at)
                ON CONFLICT DO NOTHING
                """
            ),
            {
                'country_name': rec.get('country_name'),
                'iso2': rec.get('iso2'),
                'dial_code': rec.get('dial_code'),
                'min_digits': rec.get('min_digits'),
                'max_digits': rec.get('max_digits'),
                'is_active': bool(rec.get('is_active', True)),
                'created_at': now,
                'updated_at': now,
            },
        )


def downgrade() -> None:
    op.drop_constraint('uq_country_dial_code_iso2', 'country_code_dictionary', type_='unique')
    op.drop_constraint('uq_country_iso2', 'country_code_dictionary', type_='unique')
    op.drop_table('country_code_dictionary')


