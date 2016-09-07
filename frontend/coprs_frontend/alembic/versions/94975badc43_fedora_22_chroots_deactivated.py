"""fedora-22 chroots deactivated

Revision ID: 94975badc43
Revises: 1ae2302aa2e6
Create Date: 2016-09-07 15:00:43.217280

"""

# revision identifiers, used by Alembic.
revision = '94975badc43'
down_revision = '1ae2302aa2e6'

from alembic import op
import sqlalchemy as sa


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
