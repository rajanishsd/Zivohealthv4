"""
Add goal_name and goal_description to nutrition_goals, drop objective_code and related FK/index.

Revision ID: 026_alter_nutrition_goals_add_goal_fields
Revises: 025_seed_nutrition_catalog
Create Date: 2025-09-05
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '026_add_goal_fields'
down_revision = '025_seed_nutrition_catalog'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Add new columns
    op.add_column('nutrition_goals', sa.Column('goal_name', sa.String(), nullable=True))
    op.add_column('nutrition_goals', sa.Column('goal_description', sa.Text(), nullable=True))

    # 2) Backfill goal_name/description from nutrition_objectives when possible
    op.execute(
        sa.text(
            """
            UPDATE nutrition_goals ng
            SET goal_name = COALESCE(no.display_name, 'Custom'),
                goal_description = COALESCE(no.description, ng.goal_description)
            FROM nutrition_objectives no
            WHERE ng.objective_code = no.code
            """
        )
    )
    # Ensure non-null goal_name
    op.execute(sa.text("UPDATE nutrition_goals SET goal_name = COALESCE(goal_name, 'Custom')"))

    # 3) Drop index referencing objective_code if exists
    try:
        op.drop_index('idx_nutrition_goal_user_objective_status', table_name='nutrition_goals')
    except Exception:
        # Index name may not exist in some envs; ignore
        pass

    # 4) Drop foreign key constraint on objective_code if named; try generic way
    conn = op.get_bind()
    insp = sa.inspect(conn)
    fks = insp.get_foreign_keys('nutrition_goals')
    for fk in fks:
        if 'objective_code' in fk.get('constrained_columns', []):
            op.drop_constraint(fk['name'], 'nutrition_goals', type_='foreignkey')

    # 5) Drop the objective_code column
    with op.batch_alter_table('nutrition_goals') as batch_op:
        try:
            batch_op.drop_column('objective_code')
        except Exception:
            pass

    # 6) Make goal_name non-null after backfill
    with op.batch_alter_table('nutrition_goals') as batch_op:
        batch_op.alter_column('goal_name', existing_type=sa.String(), nullable=False)


def downgrade() -> None:
    # 1) Recreate objective_code column (nullable initially)
    with op.batch_alter_table('nutrition_goals') as batch_op:
        batch_op.add_column(sa.Column('objective_code', sa.String(), nullable=True))

    # 2) Attempt to backfill objective_code from goal_name via simple mapping
    # Map some common names back to codes; otherwise set to 'custom'
    mapping = {
        'Weight Management': 'weight_management',
        'Weight Gain': 'weight_gain_diet',
        'Diabetic Diet': 'diabetic_diet',
        'Therapeutic Diet': 'therapeutic_diet',
        'Healthy Skin Diet': 'healthy_skin_diet',
        'Detox Diet': 'detox_diet',
    }
    # Build CASE expression
    cases = ' '.join([f"WHEN goal_name = '{k}' THEN '{v}'" for k, v in mapping.items()])
    op.execute(sa.text(
        f"""
        UPDATE nutrition_goals
        SET objective_code = (
            CASE {cases} ELSE 'custom' END
        )
        """
    ))

    # 3) Recreate FK to nutrition_objectives.code and index
    try:
        op.create_foreign_key(None, 'nutrition_goals', 'nutrition_objectives', ['objective_code'], ['code'])
    except Exception:
        pass
    try:
        op.create_index('idx_nutrition_goal_user_objective_status', 'nutrition_goals', ['user_id', 'objective_code', 'status'])
    except Exception:
        pass

    # 4) Drop new columns
    with op.batch_alter_table('nutrition_goals') as batch_op:
        try:
            batch_op.drop_column('goal_description')
        except Exception:
            pass
        try:
            batch_op.drop_column('goal_name')
        except Exception:
            pass

