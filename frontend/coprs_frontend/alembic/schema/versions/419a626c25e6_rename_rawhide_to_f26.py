"""Rename rawhide to f26

Revision ID: 419a626c25e6
Revises: 149da7c4ac2f
Create Date: 2016-10-05 13:16:21.428071

"""

# revision identifiers, used by Alembic.
revision = '419a626c25e6'
down_revision = '149da7c4ac2f'

from alembic import op
import sqlalchemy as sa


def upgrade():
    """ Moved to coprs_frontend/alembic/fedora/versions """
    pass


def downgrade():
    """ Moved to coprs_frontend/alembic/fedora/versions """
    pass
