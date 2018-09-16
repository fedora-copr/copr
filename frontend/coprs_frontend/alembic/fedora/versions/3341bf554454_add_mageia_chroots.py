"""add mageia chroots

Revision ID: 3341bf554454
Revises: 94975badc43
Create Date: 2016-09-20 19:28:16.115630

"""

# revision identifiers, used by Alembic.
revision = '3341bf554454'
down_revision = '94975badc43'

from alembic import op


def upgrade():
    bind = op.get_bind()
    connection = bind.connect()

    connection.execute(
        "INSERT INTO mock_chroot(os_release, os_version, arch, is_active) VALUES ('mageia', '6', 'x86_64', True)"
    )
    connection.execute(
        "INSERT INTO mock_chroot(os_release, os_version, arch, is_active) VALUES ('mageia', '6', 'i586', True)"
    )
    connection.execute(
        "INSERT INTO mock_chroot(os_release, os_version, arch, is_active) VALUES ('mageia', 'cauldron', 'x86_64', True)"
    )
    connection.execute(
        "INSERT INTO mock_chroot(os_release, os_version, arch, is_active) VALUES ('mageia', 'cauldron', 'i586', True)"
    )
    connection.close()


def downgrade():
    bind = op.get_bind()
    connection = bind.connect()

    connection.execute( # there might be already referencing records so just set is_active to False instead of removing
        "UPDATE mock_chroot SET is_active=False WHERE os_release = 'mageia'"
    )
    connection.close()
