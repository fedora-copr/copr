"""Rename rawhide to f26

Revision ID: 419a626c25e6
Revises: 8de41eec1d1
Create Date: 2016-10-05 13:16:21.428071

"""

# revision identifiers, used by Alembic.
revision = '419a626c25e6'
down_revision = '8de41eec1d1'

from alembic import op


def upgrade():
    bind = op.get_bind()
    connection = bind.connect()

    connection.execute(
        "UPDATE mock_chroot SET os_version='26' WHERE os_release = 'fedora' AND os_version = 'rawhide'"
    )
    connection.close()


def downgrade():
    bind = op.get_bind()
    connection = bind.connect()

    connection.execute(
        "UPDATE mock_chroot SET os_version='rawhide' WHERE os_release = 'fedora' AND os_version = '26'"
    )
    connection.close()
