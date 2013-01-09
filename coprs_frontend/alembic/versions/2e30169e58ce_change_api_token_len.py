"""Change api_token length from varchar(40) to varchar(255)

Revision ID: 2e30169e58ce
Revises: 32ba137a3d56
Create Date: 2013-01-08 19:42:16.562926

"""

# revision identifiers, used by Alembic.
revision = '2e30169e58ce'
down_revision = '32ba137a3d56'

from alembic import op
import sqlalchemy as sa


def upgrade():
    """ Change the api_token field from the user table from varchar(40) to
    varchar(255).
    """
    op.alter_column("user", "api_token", type_=sa.String(255))


def downgrade():
    """ Change the api_token field from the user table from varchar(255) to
    varchar(40).
    """
    op.alter_column("user", "api_token", type_=sa.String(40))
