"""enabling fedora-25 chroots

Revision ID: 8de41eec1d1
Revises: 94975badc43
Create Date: 2016-09-07 15:41:35.130578

"""

# revision identifiers, used by Alembic.
revision = '8de41eec1d1'
down_revision = '94975badc43'

from alembic import op
import sqlalchemy as sa


def upgrade():
    """ Moved to coprs_frontend/alembic/fedora/versions """
    pass


def downgrade():
    """ Moved to coprs_frontend/alembic/fedora/versions """
    pass
