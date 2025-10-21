"""normalize mental health entries to reference dictionary ids

Revision ID: 061
Revises: 060
Create Date: 2025-10-14 13:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '061'
down_revision = '060'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns
    op.add_column('mental_health_entries', sa.Column('pleasantness_id', sa.Integer(), nullable=True))
    op.add_column('mental_health_entries', sa.Column('entry_type_id', sa.Integer(), nullable=True))
    op.create_index('ix_mh_entries_pleasantness_id', 'mental_health_entries', ['pleasantness_id'])
    op.create_index('ix_mh_entries_entry_type_id', 'mental_health_entries', ['entry_type_id'])
    op.create_foreign_key('fk_mh_entries_pleasantness', 'mental_health_entries', 'mental_health_pleasantness_dictionary', ['pleasantness_id'], ['id'])
    op.create_foreign_key('fk_mh_entries_entry_type', 'mental_health_entries', 'mental_health_entry_type_dictionary', ['entry_type_id'], ['id'])

    # Create association tables
    op.create_table(
        'mental_health_entry_feelings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('entry_id', sa.Integer(), nullable=False),
        sa.Column('feeling_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['entry_id'], ['mental_health_entries.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['feeling_id'], ['mental_health_feelings_dictionary.id'], ondelete='CASCADE')
    )
    op.create_index('ix_mh_entry_feelings_entry_id', 'mental_health_entry_feelings', ['entry_id'])
    op.create_index('ix_mh_entry_feelings_feeling_id', 'mental_health_entry_feelings', ['feeling_id'])

    op.create_table(
        'mental_health_entry_impacts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('entry_id', sa.Integer(), nullable=False),
        sa.Column('impact_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['entry_id'], ['mental_health_entries.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['impact_id'], ['mental_health_impacts_dictionary.id'], ondelete='CASCADE')
    )
    op.create_index('ix_mh_entry_impacts_entry_id', 'mental_health_entry_impacts', ['entry_id'])
    op.create_index('ix_mh_entry_impacts_impact_id', 'mental_health_entry_impacts', ['impact_id'])

    # Optional: backfill ids for existing rows using available labels and codes
    op.execute(
        """
        UPDATE mental_health_entries e
        SET pleasantness_id = p.id
        FROM mental_health_pleasantness_dictionary p
        WHERE e.pleasantness_score = p.score;
        """
    )
    op.execute(
        """
        UPDATE mental_health_entries e
        SET entry_type_id = t.id
        FROM mental_health_entry_type_dictionary t
        WHERE e.entry_type = t.code;
        """
    )


def downgrade() -> None:
    op.drop_index('ix_mh_entry_impacts_impact_id', table_name='mental_health_entry_impacts')
    op.drop_index('ix_mh_entry_impacts_entry_id', table_name='mental_health_entry_impacts')
    op.drop_table('mental_health_entry_impacts')
    op.drop_index('ix_mh_entry_feelings_feeling_id', table_name='mental_health_entry_feelings')
    op.drop_index('ix_mh_entry_feelings_entry_id', table_name='mental_health_entry_feelings')
    op.drop_table('mental_health_entry_feelings')
    op.drop_constraint('fk_mh_entries_entry_type', 'mental_health_entries', type_='foreignkey')
    op.drop_constraint('fk_mh_entries_pleasantness', 'mental_health_entries', type_='foreignkey')
    op.drop_index('ix_mh_entries_entry_type_id', table_name='mental_health_entries')
    op.drop_index('ix_mh_entries_pleasantness_id', table_name='mental_health_entries')
    op.drop_column('mental_health_entries', 'entry_type_id')
    op.drop_column('mental_health_entries', 'pleasantness_id')


