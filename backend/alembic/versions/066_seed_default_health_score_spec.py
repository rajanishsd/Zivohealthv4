"""seed default health score spec v1

Revision ID: 066
Revises: 065
Create Date: 2025-10-15 12:05:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert
import json


# revision identifiers, used by Alembic.
revision = '066'
down_revision = '065'
branch_labels = None
depends_on = None


def upgrade() -> None:
    spec = {
        "specVersion": "1.0.0",
        "updated": "2025-10-15",
        "scoring": {
            "overall": {
                "blend": {"chronic": 0.7, "acute": 0.3},
                "acuteWeights": {"vitals_today": 0.40, "sleep_last_night": 0.35, "activity_today": 0.25},
                "chronicWeightsByAge": {
                    "18-39": {"biomarkers": 0.25, "vitals_30d": 0.10, "activity": 0.20, "sleep": 0.17, "nutrition": 0.18, "medications": 0.10},
                    "40-64": {"biomarkers": 0.35, "vitals_30d": 0.10, "activity": 0.15, "sleep": 0.15, "nutrition": 0.15, "medications": 0.10},
                    "65+": {"biomarkers": 0.45, "vitals_30d": 0.15, "activity": 0.10, "sleep": 0.10, "nutrition": 0.10, "medications": 0.10}
                }
            }
        },
        "modalities": {},
        "ageSexAdjustments": {},
        "explainability": {"topDrivers": 3}
    }

    conn = op.get_bind()
    metadata = sa.MetaData()
    specs = sa.Table(
        'health_score_specs', metadata,
        sa.Column('id', sa.Integer),
        sa.Column('version', sa.String(32)),
        sa.Column('name', sa.String(128)),
        sa.Column('spec_json', postgresql.JSONB),
        sa.Column('is_default', sa.Boolean),
    )
    stmt = insert(specs).values(
        version='v1',
        name='Default Health Score Spec v1',
        spec_json=spec,
        is_default=True,
    ).on_conflict_do_update(
        index_elements=['version'],
        set_={'name': 'Default Health Score Spec v1', 'spec_json': spec, 'is_default': True}
    )
    conn.execute(stmt)


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM health_score_specs WHERE version = 'v1'"))


