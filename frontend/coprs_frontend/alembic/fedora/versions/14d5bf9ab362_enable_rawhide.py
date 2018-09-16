"""enable_rawhide

Revision ID: 14d5bf9ab362
Revises: 419a626c25e6
Create Date: 2017-02-27 10:10:37.158399

"""

# revision identifiers, used by Alembic.
revision = '14d5bf9ab362'
down_revision = '419a626c25e6'

from alembic import op


def upgrade():
    bind = op.get_bind()
    connection = bind.connect()

    connection.execute(
        "INSERT INTO mock_chroot (\"os_release\", \"os_version\", \"arch\", \"is_active\") VALUES('fedora', 'rawhide', 'x86_64', True) ON CONFLICT ON CONSTRAINT mock_chroot_uniq DO UPDATE SET is_active=True;"
    )
    connection.execute(
        "INSERT INTO mock_chroot (\"os_release\", \"os_version\", \"arch\", \"is_active\") VALUES('fedora', 'rawhide', 'i386', True) ON CONFLICT ON CONSTRAINT mock_chroot_uniq DO UPDATE SET is_active=True;"
    )
    connection.execute(
        "INSERT INTO mock_chroot (\"os_release\", \"os_version\", \"arch\", \"is_active\") VALUES('fedora', 'rawhide', 'ppc64le', True) ON CONFLICT ON CONSTRAINT mock_chroot_uniq DO UPDATE SET is_active=True;"
    )
    connection.close()


def downgrade():
    bind = op.get_bind()
    connection = bind.connect()

    connection.execute( # there might be already referencing records so just set is_active to False instead of removing
        "UPDATE mock_chroot SET is_active=False WHERE os_release = 'fedora' AND os_version = 'rawhide'"
    )
    connection.close()
