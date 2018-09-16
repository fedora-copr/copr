"""enabling fedora-25 chroots

Revision ID: 8de41eec1d1
Revises: 3341bf554454
Create Date: 2016-09-07 15:41:35.130578

"""

# revision identifiers, used by Alembic.
revision = '8de41eec1d1'
down_revision = '3341bf554454'

from alembic import op


def upgrade():
    bind = op.get_bind()
    connection = bind.connect()

    connection.execute(
        "INSERT INTO mock_chroot(os_release, os_version, arch, is_active) VALUES ('fedora', '25', 'x86_64', True)"
    )
    connection.execute(
        "INSERT INTO mock_chroot(os_release, os_version, arch, is_active) VALUES ('fedora', '25', 'i386', True)"
    )
    connection.execute(
        "INSERT INTO mock_chroot(os_release, os_version, arch, is_active) VALUES ('fedora', '25', 'ppc64le', True)"
    )
    connection.close()


def downgrade():
    bind = op.get_bind()
    connection = bind.connect()

    connection.execute( # there might be already referencing records so just set is_active to False instead of removing
        "UPDATE mock_chroot SET is_active=False WHERE os_release = 'fedora' AND os_version = '25'"
    )
    connection.close()
