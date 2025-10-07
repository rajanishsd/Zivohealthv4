"""
add timezone dictionary table

Revision ID: 051_add_timezone_dictionary
Revises: 050_split_user_names
Create Date: 2025-01-27 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '051_add_timezone_dictionary'
down_revision = '050_split_user_names'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create timezone dictionary table
    op.create_table('timezone_dictionary',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('identifier', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('utc_offset', sa.String(length=10), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('identifier')
    )
    
    # Add timezone_id foreign key to users table
    op.add_column('users', sa.Column('timezone_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_users_timezone', 'users', 'timezone_dictionary', ['timezone_id'], ['id'])
    
    # Add timezone_id foreign key to user_profiles table
    op.add_column('user_profiles', sa.Column('timezone_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_user_profiles_timezone', 'user_profiles', 'timezone_dictionary', ['timezone_id'], ['id'])
    
    # Add timezone_id foreign key to doctors table
    op.add_column('doctors', sa.Column('timezone_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_doctors_timezone', 'doctors', 'timezone_dictionary', ['timezone_id'], ['id'])
    
    # Add timezone_id foreign key to admins table
    op.add_column('admins', sa.Column('timezone_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_admins_timezone', 'admins', 'timezone_dictionary', ['timezone_id'], ['id'])

    # Insert common timezones
    conn = op.get_bind()
    
    timezones = [
        # UTC
        ('UTC', 'UTC (Coordinated Universal Time)', '+00:00'),
        # Americas
        ('America/New_York', 'Eastern Time (US & Canada)', '-05:00'),
        ('America/Chicago', 'Central Time (US & Canada)', '-06:00'),
        ('America/Denver', 'Mountain Time (US & Canada)', '-07:00'),
        ('America/Los_Angeles', 'Pacific Time (US & Canada)', '-08:00'),
        ('America/Toronto', 'Toronto', '-05:00'),
        ('America/Vancouver', 'Vancouver', '-08:00'),
        ('America/Mexico_City', 'Mexico City', '-06:00'),
        ('America/Sao_Paulo', 'São Paulo', '-03:00'),
        ('America/Argentina/Buenos_Aires', 'Buenos Aires', '-03:00'),
        # Europe
        ('Europe/London', 'London', '+00:00'),
        ('Europe/Paris', 'Paris', '+01:00'),
        ('Europe/Berlin', 'Berlin', '+01:00'),
        ('Europe/Rome', 'Rome', '+01:00'),
        ('Europe/Madrid', 'Madrid', '+01:00'),
        ('Europe/Amsterdam', 'Amsterdam', '+01:00'),
        ('Europe/Zurich', 'Zurich', '+01:00'),
        ('Europe/Vienna', 'Vienna', '+01:00'),
        ('Europe/Stockholm', 'Stockholm', '+01:00'),
        ('Europe/Oslo', 'Oslo', '+01:00'),
        ('Europe/Copenhagen', 'Copenhagen', '+01:00'),
        ('Europe/Helsinki', 'Helsinki', '+02:00'),
        ('Europe/Warsaw', 'Warsaw', '+01:00'),
        ('Europe/Prague', 'Prague', '+01:00'),
        ('Europe/Budapest', 'Budapest', '+01:00'),
        ('Europe/Athens', 'Athens', '+02:00'),
        ('Europe/Istanbul', 'Istanbul', '+03:00'),
        ('Europe/Moscow', 'Moscow', '+03:00'),
        # Asia
        ('Asia/Tokyo', 'Tokyo', '+09:00'),
        ('Asia/Shanghai', 'Shanghai', '+08:00'),
        ('Asia/Hong_Kong', 'Hong Kong', '+08:00'),
        ('Asia/Singapore', 'Singapore', '+08:00'),
        ('Asia/Seoul', 'Seoul', '+09:00'),
        ('Asia/Taipei', 'Taipei', '+08:00'),
        ('Asia/Bangkok', 'Bangkok', '+07:00'),
        ('Asia/Jakarta', 'Jakarta', '+07:00'),
        ('Asia/Manila', 'Manila', '+08:00'),
        ('Asia/Kolkata', 'New Delhi', '+05:30'),
        ('Asia/Karachi', 'Karachi', '+05:00'),
        ('Asia/Dubai', 'Dubai', '+04:00'),
        ('Asia/Tehran', 'Tehran', '+03:30'),
        ('Asia/Jerusalem', 'Jerusalem', '+02:00'),
        # Africa
        ('Africa/Cairo', 'Cairo', '+02:00'),
        ('Africa/Johannesburg', 'Johannesburg', '+02:00'),
        ('Africa/Lagos', 'Lagos', '+01:00'),
        ('Africa/Casablanca', 'Casablanca', '+00:00'),
        # Australia/Oceania
        ('Australia/Sydney', 'Sydney', '+10:00'),
        ('Australia/Melbourne', 'Melbourne', '+10:00'),
        ('Australia/Perth', 'Perth', '+08:00'),
        ('Australia/Adelaide', 'Adelaide', '+09:30'),
        ('Pacific/Auckland', 'Auckland', '+12:00'),
        ('Pacific/Honolulu', 'Honolulu', '-10:00'),
    ]
    
    for identifier, display_name, utc_offset in timezones:
        conn.execute(sa.text("""
            INSERT INTO timezone_dictionary (identifier, display_name, utc_offset, is_active, created_at, updated_at)
            VALUES (:identifier, :display_name, :utc_offset, true, NOW(), NOW())
        """), {
            'identifier': identifier,
            'display_name': display_name,
            'utc_offset': utc_offset
        })


def downgrade() -> None:
    # Drop foreign key constraints
    op.drop_constraint('fk_admins_timezone', 'admins', type_='foreignkey')
    op.drop_constraint('fk_doctors_timezone', 'doctors', type_='foreignkey')
    op.drop_constraint('fk_user_profiles_timezone', 'user_profiles', type_='foreignkey')
    op.drop_constraint('fk_users_timezone', 'users', type_='foreignkey')
    
    # Drop timezone_id columns
    op.drop_column('admins', 'timezone_id')
    op.drop_column('doctors', 'timezone_id')
    op.drop_column('user_profiles', 'timezone_id')
    op.drop_column('users', 'timezone_id')
    
    # Drop timezone dictionary table
    op.drop_table('timezone_dictionary')
