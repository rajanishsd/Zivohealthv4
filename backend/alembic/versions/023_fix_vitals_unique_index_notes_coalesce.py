"""Fix vitals unique constraint by coalescing notes to empty string

Revision ID: 023
Revises: 022
Create Date: 2025-08-30 09:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '023'
down_revision = '022'
branch_labels = None
depends_on = None


def upgrade():
    # 1) Remove duplicates keeping the lowest id per composite key while treating NULL notes as ''
    op.execute(
        """
        DELETE FROM vitals_raw_data vrd
        USING (
            SELECT MIN(id) AS keep_id
            FROM vitals_raw_data
            GROUP BY user_id, metric_type, unit, start_date, data_source, COALESCE(notes, '')
        ) AS keepers
        WHERE vrd.id <> keepers.keep_id
          AND vrd.user_id = (SELECT user_id FROM vitals_raw_data WHERE id = keepers.keep_id)
          AND vrd.metric_type = (SELECT metric_type FROM vitals_raw_data WHERE id = keepers.keep_id)
          AND vrd.unit = (SELECT unit FROM vitals_raw_data WHERE id = keepers.keep_id)
          AND vrd.start_date = (SELECT start_date FROM vitals_raw_data WHERE id = keepers.keep_id)
          AND vrd.data_source = (SELECT data_source FROM vitals_raw_data WHERE id = keepers.keep_id)
          AND COALESCE(vrd.notes, '') = (SELECT COALESCE(notes, '') FROM vitals_raw_data WHERE id = keepers.keep_id)
        ;
        """
    )

    # 2) Drop the existing named unique constraint if it exists
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                WHERE c.conname = 'uq_vitals_raw_data_no_duplicates'
                  AND t.relname = 'vitals_raw_data'
            ) THEN
                ALTER TABLE vitals_raw_data DROP CONSTRAINT uq_vitals_raw_data_no_duplicates;
            END IF;
        END$$;
        """
    )

    # 3) Create a functional unique index that treats NULL notes as ''
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_vitals_raw_data_nodups
        ON vitals_raw_data (user_id, metric_type, unit, start_date, data_source, COALESCE(notes, ''));
        """
    )


def downgrade():
    # Drop the functional index
    op.execute("DROP INDEX IF EXISTS ux_vitals_raw_data_nodups;")

    # Recreate the old unique constraint
    op.create_unique_constraint(
        'uq_vitals_raw_data_no_duplicates',
        'vitals_raw_data',
        ['user_id', 'metric_type', 'unit', 'start_date', 'data_source', 'notes']
    )


