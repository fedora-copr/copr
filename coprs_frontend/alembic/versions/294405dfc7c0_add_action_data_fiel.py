"""add Action.data field

Revision ID: 294405dfc7c0
Revises: 3a415c6392bc
Create Date: 2014-01-20 15:43:09.986912

"""

# revision identifiers, used by Alembic.
revision = "294405dfc7c0"
down_revision = "3a415c6392bc"

from alembic import op
import sqlalchemy as sa


def upgrade():
    """ Add "data" colum to action table. """
    op.add_column("action", sa.Column("data", sa.Text()))


def downgrade():
    """ Drop "data" colum from action table. """
    op.drop_column("action", "data")
