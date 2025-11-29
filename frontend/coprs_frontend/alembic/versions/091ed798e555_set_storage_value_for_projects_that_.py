"""
Set storage value for projects that predate Pulp

Revision ID: 091ed798e555
Create Date: 2025-12-02 21:18:12.747970
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '091ed798e555'
down_revision = 'bb52d9f878f5'
branch_labels = None
depends_on = None


def upgrade():
    session = sa.orm.sessionmaker(bind=op.get_bind())()
    sql = "UPDATE copr SET storage=0 WHERE storage IS NULL"
    session.execute(sa.text(sql))


def downgrade():
    """
    There is no way back
    """
