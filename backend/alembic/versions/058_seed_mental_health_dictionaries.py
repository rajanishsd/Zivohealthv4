"""seed mental health dictionaries

Revision ID: 058
Revises: 057
Create Date: 2025-10-14 12:14:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '058'
down_revision = '057'
branch_labels = None
depends_on = None


FEELINGS = [
    "Amazed","Amused","Angry","Annoyed","Anxious","Ashamed","Brave","Calm",
    "Confident","Content","Disappointed","Discouraged","Disgusted","Drained",
    "Embarrassed","Excited","Frustrated","Grateful","Guilty","Happy","Hopeful",
    "Hopeless","Indifferent","Irritated","Jealous","Joyful","Lonely",
    "Overwhelmed","Passionate","Peaceful","Proud","Relieved","Sad","Satisfied",
    "Scared","Stressed","Surprised","Worried"
]

IMPACTS = [
    "Health","Fitness","Self-Care","Hobbies","Identity","Spirituality",
    "Community","Family","Friends","Partner","Dating","Tasks","Work",
    "Education","Travel","Weather","Current Events","Money"
]


def upgrade() -> None:
    conn = op.get_bind()
    # Insert feelings if table exists
    for i, name in enumerate(FEELINGS):
        conn.execute(sa.text(
            "INSERT INTO mental_health_feelings_dictionary (name, is_active, sort_order)"
            " VALUES (:name, 'true', :sort) ON CONFLICT (name) DO NOTHING"
        ), {"name": name, "sort": i})

    for i, name in enumerate(IMPACTS):
        conn.execute(sa.text(
            "INSERT INTO mental_health_impacts_dictionary (name, is_active, sort_order)"
            " VALUES (:name, 'true', :sort) ON CONFLICT (name) DO NOTHING"
        ), {"name": name, "sort": i})


def downgrade() -> None:
    conn = op.get_bind()
    for name in FEELINGS:
        conn.execute(sa.text("DELETE FROM mental_health_feelings_dictionary WHERE name=:name"), {"name": name})
    for name in IMPACTS:
        conn.execute(sa.text("DELETE FROM mental_health_impacts_dictionary WHERE name=:name"), {"name": name})


