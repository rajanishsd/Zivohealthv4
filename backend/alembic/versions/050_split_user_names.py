"""
split user and profile names into first/middle/last

Revision ID: 050_split_user_names
Revises: 049_add_user_notification_fields
Create Date: 2025-10-07 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '050_split_user_names'
down_revision = '049_add_user_notification_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to users
    op.add_column('users', sa.Column('first_name', sa.String(), nullable=True))
    op.add_column('users', sa.Column('middle_name', sa.String(), nullable=True))
    op.add_column('users', sa.Column('last_name', sa.String(), nullable=True))

    # Add new columns to user_profiles
    op.add_column('user_profiles', sa.Column('first_name', sa.String(length=255), nullable=True))
    op.add_column('user_profiles', sa.Column('middle_name', sa.String(length=255), nullable=True))
    op.add_column('user_profiles', sa.Column('last_name', sa.String(length=255), nullable=True))

    # Add new columns to doctors
    op.add_column('doctors', sa.Column('first_name', sa.String(), nullable=True))
    op.add_column('doctors', sa.Column('middle_name', sa.String(), nullable=True))
    op.add_column('doctors', sa.Column('last_name', sa.String(), nullable=True))

    # Add new columns to admins
    op.add_column('admins', sa.Column('first_name', sa.String(length=255), nullable=True))
    op.add_column('admins', sa.Column('middle_name', sa.String(length=255), nullable=True))
    op.add_column('admins', sa.Column('last_name', sa.String(length=255), nullable=True))

    # Backfill from full_name where present (PostgreSQL-specific functions)
    conn = op.get_bind()

    # Users table backfill
    conn.execute(sa.text(
        """
        UPDATE users
        SET
            first_name = CASE
                WHEN full_name IS NULL OR btrim(full_name) = '' THEN NULL
                ELSE (regexp_split_to_array(btrim(full_name), '\\s+'))[1]
            END,
            last_name = CASE
                WHEN full_name IS NULL OR btrim(full_name) = '' THEN NULL
                ELSE (
                    CASE 
                        WHEN cardinality(regexp_split_to_array(btrim(full_name), '\\s+')) > 1
                        THEN (regexp_split_to_array(btrim(full_name), '\\s+'))[cardinality(regexp_split_to_array(btrim(full_name), '\\s+'))]
                        ELSE NULL
                    END
                )
            END,
            middle_name = CASE
                WHEN full_name IS NULL OR btrim(full_name) = '' THEN NULL
                ELSE (
                    CASE 
                        WHEN cardinality(regexp_split_to_array(btrim(full_name), '\\s+')) > 2
                        THEN array_to_string((regexp_split_to_array(btrim(full_name), '\\s+'))[2:cardinality(regexp_split_to_array(btrim(full_name), '\\s+'))-1], ' ')
                        ELSE NULL
                    END
                )
            END
        WHERE full_name IS NOT NULL AND btrim(full_name) <> ''
        """
    ))

    # User profiles table backfill
    conn.execute(sa.text(
        """
        UPDATE user_profiles
        SET
            first_name = CASE
                WHEN full_name IS NULL OR btrim(full_name) = '' THEN NULL
                ELSE (regexp_split_to_array(btrim(full_name), '\\s+'))[1]
            END,
            last_name = CASE
                WHEN full_name IS NULL OR btrim(full_name) = '' THEN NULL
                ELSE (
                    CASE 
                        WHEN cardinality(regexp_split_to_array(btrim(full_name), '\\s+')) > 1
                        THEN (regexp_split_to_array(btrim(full_name), '\\s+'))[cardinality(regexp_split_to_array(btrim(full_name), '\\s+'))]
                        ELSE NULL
                    END
                )
            END,
            middle_name = CASE
                WHEN full_name IS NULL OR btrim(full_name) = '' THEN NULL
                ELSE (
                    CASE 
                        WHEN cardinality(regexp_split_to_array(btrim(full_name), '\\s+')) > 2
                        THEN array_to_string((regexp_split_to_array(btrim(full_name), '\\s+'))[2:cardinality(regexp_split_to_array(btrim(full_name), '\\s+'))-1], ' ')
                        ELSE NULL
                    END
                )
            END
        WHERE full_name IS NOT NULL AND btrim(full_name) <> ''
        """
    ))

    # Doctors table backfill
    conn.execute(sa.text(
        """
        UPDATE doctors
        SET
            first_name = CASE
                WHEN full_name IS NULL OR btrim(full_name) = '' THEN NULL
                ELSE (regexp_split_to_array(btrim(full_name), '\\s+'))[1]
            END,
            last_name = CASE
                WHEN full_name IS NULL OR btrim(full_name) = '' THEN NULL
                ELSE (
                    CASE 
                        WHEN cardinality(regexp_split_to_array(btrim(full_name), '\\s+')) > 1
                        THEN (regexp_split_to_array(btrim(full_name), '\\s+'))[cardinality(regexp_split_to_array(btrim(full_name), '\\s+'))]
                        ELSE NULL
                    END
                )
            END,
            middle_name = CASE
                WHEN full_name IS NULL OR btrim(full_name) = '' THEN NULL
                ELSE (
                    CASE 
                        WHEN cardinality(regexp_split_to_array(btrim(full_name), '\\s+')) > 2
                        THEN array_to_string((regexp_split_to_array(btrim(full_name), '\\s+'))[2:cardinality(regexp_split_to_array(btrim(full_name), '\\s+'))-1], ' ')
                        ELSE NULL
                    END
                )
            END
        WHERE full_name IS NOT NULL AND btrim(full_name) <> ''
        """
    ))

    # Admins table backfill
    conn.execute(sa.text(
        """
        UPDATE admins
        SET
            first_name = CASE
                WHEN full_name IS NULL OR btrim(full_name) = '' THEN NULL
                ELSE (regexp_split_to_array(btrim(full_name), '\\s+'))[1]
            END,
            last_name = CASE
                WHEN full_name IS NULL OR btrim(full_name) = '' THEN NULL
                ELSE (
                    CASE 
                        WHEN cardinality(regexp_split_to_array(btrim(full_name), '\\s+')) > 1
                        THEN (regexp_split_to_array(btrim(full_name), '\\s+'))[cardinality(regexp_split_to_array(btrim(full_name), '\\s+'))]
                        ELSE NULL
                    END
                )
            END,
            middle_name = CASE
                WHEN full_name IS NULL OR btrim(full_name) = '' THEN NULL
                ELSE (
                    CASE 
                        WHEN cardinality(regexp_split_to_array(btrim(full_name), '\\s+')) > 2
                        THEN array_to_string((regexp_split_to_array(btrim(full_name), '\\s+'))[2:cardinality(regexp_split_to_array(btrim(full_name), '\\s+'))-1], ' ')
                        ELSE NULL
                    END
                )
            END
        WHERE full_name IS NOT NULL AND btrim(full_name) <> ''
        """
    ))

    # Drop old columns
    op.drop_column('user_profiles', 'full_name')
    op.drop_column('users', 'full_name')
    op.drop_column('doctors', 'full_name')
    op.drop_column('admins', 'full_name')


def downgrade() -> None:
    # Recreate full_name columns
    op.add_column('users', sa.Column('full_name', sa.String(), nullable=True))
    op.add_column('user_profiles', sa.Column('full_name', sa.String(length=255), nullable=True))
    op.add_column('doctors', sa.Column('full_name', sa.String(), nullable=True))
    op.add_column('admins', sa.Column('full_name', sa.String(length=255), nullable=True))

    conn = op.get_bind()

    # Populate full_name from parts (trim extra spaces)
    conn.execute(sa.text(
        """
        UPDATE users
        SET full_name = btrim(
            coalesce(first_name, '') ||
            CASE WHEN coalesce(middle_name, '') <> '' THEN ' ' || middle_name ELSE '' END ||
            CASE WHEN coalesce(last_name, '') <> '' THEN ' ' || last_name ELSE '' END
        )
        """
    ))

    conn.execute(sa.text(
        """
        UPDATE user_profiles
        SET full_name = btrim(
            coalesce(first_name, '') ||
            CASE WHEN coalesce(middle_name, '') <> '' THEN ' ' || middle_name ELSE '' END ||
            CASE WHEN coalesce(last_name, '') <> '' THEN ' ' || last_name ELSE '' END
        )
        """
    ))

    conn.execute(sa.text(
        """
        UPDATE doctors
        SET full_name = btrim(
            coalesce(first_name, '') ||
            CASE WHEN coalesce(middle_name, '') <> '' THEN ' ' || middle_name ELSE '' END ||
            CASE WHEN coalesce(last_name, '') <> '' THEN ' ' || last_name ELSE '' END
        )
        """
    ))

    conn.execute(sa.text(
        """
        UPDATE admins
        SET full_name = btrim(
            coalesce(first_name, '') ||
            CASE WHEN coalesce(middle_name, '') <> '' THEN ' ' || middle_name ELSE '' END ||
            CASE WHEN coalesce(last_name, '') <> '' THEN ' ' || last_name ELSE '' END
        )
        """
    ))

    # Drop split columns
    op.drop_column('user_profiles', 'last_name')
    op.drop_column('user_profiles', 'middle_name')
    op.drop_column('user_profiles', 'first_name')
    op.drop_column('doctors', 'last_name')
    op.drop_column('doctors', 'middle_name')
    op.drop_column('doctors', 'first_name')
    op.drop_column('admins', 'last_name')
    op.drop_column('admins', 'middle_name')
    op.drop_column('admins', 'first_name')
    op.drop_column('users', 'last_name')
    op.drop_column('users', 'middle_name')
    op.drop_column('users', 'first_name')


