"""status_to_order function

Revision ID: 19ca0c14096e
Revises: 3ec22e1db75a
Create Date: 2015-11-16 21:20:46.498155

"""

# revision identifiers, used by Alembic.
revision = '19ca0c14096e'
down_revision = '3ec22e1db75a'

from alembic import op
import sqlalchemy as sa

from coprs.logic.builds_logic import BuildsLogic

def upgrade():
    BuildsLogic.init_db()


def downgrade():
    query = """DROP FUNCTION status_to_order (x integer);
		DROP FUNCTION order_to_status (x integer);
		"""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text(query))
