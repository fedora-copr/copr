"""
Switch packages to pyp2spec

Revision ID: 43f9339a9e9a
Create Date: 2026-09-10 11:11:34.114231
"""
# pylint: disable=invalid-name

import json
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '43f9339a9e9a'
down_revision = 'e31b4af2468c'
branch_labels = None
depends_on = None


def upgrade():
    session = sa.orm.sessionmaker(bind=op.get_bind())()

    sql = "SELECT id, source_json FROM package WHERE source_type=:source_type"
    data = {"source_type": 5}
    rows = session.execute(sa.text(sql), data).mappings()
    for row in rows:
        # This should never happen
        if not row["source_json"]:
            continue

        source_dict = json.loads(row["source_json"])
        if source_dict.get("spec_generator") != "pyp2rpm":
            continue

        source_dict["spec_generator"] = "pyp2spec"

        sql = "UPDATE package SET source_json=:source_json WHERE id=:id"
        data = {
            "source_json": json.dumps(source_dict),
            "id": row["id"],
        }
        session.execute(sa.text(sql), data)


def downgrade():
    # No way back
    return
