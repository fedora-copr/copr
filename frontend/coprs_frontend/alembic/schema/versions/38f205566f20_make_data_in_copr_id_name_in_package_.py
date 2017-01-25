"""make data in (copr_id, name) in package table unique, see Bug 1382243 - Multiple rows were found for one()
   Assume that there are no two packages with the same name in the same copr both having some builds referencing them
   (otherwise manual "rebinding" of the builds to just one of the packages is needed).

Revision ID: 38f205566f20
Revises: 15852f9e313f
Create Date: 2016-10-10 14:09:03.353726

"""

# revision identifiers, used by Alembic.
revision = '38f205566f20'
down_revision = '15852f9e313f'

from alembic import op
import sqlalchemy as sa


def upgrade():
    bind = op.get_bind()
    connection = bind.connect()
    connection.execute("""
        DELETE FROM package WHERE package.id NOT IN (SELECT DISTINCT package_id FROM build WHERE package_id IS NOT NULL) AND EXISTS (SELECT id FROM package AS package2 WHERE package2.copr_id=package.copr_id AND package2.name=package.name AND package2.id!=package.id);
    """)
    connection.close()

def downgrade():
    # this migration is only one-way
    pass
