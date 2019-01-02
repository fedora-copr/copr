"""remove_build_results_column

Revision ID: 6fed8655d074
Revises: 51716ab39d37
Create Date: 2018-11-16 10:40:23.891425

"""

# revision identifiers, used by Alembic.
revision = '6fed8655d074'
down_revision = '69c5f19841a5'

from alembic import op
import sqlalchemy as sa


def upgrade():
    session = sa.orm.sessionmaker(bind=op.get_bind())()
    session.execute("ALTER TABLE build DROP COLUMN IF EXISTS results")

def downgrade():
    pass
