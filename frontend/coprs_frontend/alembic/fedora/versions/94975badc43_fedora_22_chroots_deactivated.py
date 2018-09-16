"""fedora-22 chroots deactivated

Revision ID: 94975badc43
Revises: None
Create Date: 2016-09-07 15:00:43.217280

"""

# revision identifiers, used by Alembic.
revision = '94975badc43'
down_revision = None

from alembic import op


def upgrade():
    bind = op.get_bind()
    connection = bind.connect()

    connection.execute(
        "UPDATE mock_chroot SET is_active=False WHERE os_release = 'fedora' AND os_version='22'"
    )
    connection.close()


def downgrade():
    bind = op.get_bind()
    connection = bind.connect()

    connection.execute(
        "UPDATE mock_chroot SET is_active=True WHERE os_release = 'fedora' AND os_version='22'"
    )
    connection.close()
