"""
fixup unassigned copr chroots

Revision ID: b0fd99505e37
Revises: 4d06318043d3
Create Date: 2020-04-29 08:26:46.827633
"""

from alembic import op

revision = 'b0fd99505e37'
down_revision = '4d06318043d3'

def upgrade():
    # Cancel all build_chroot instances that were submitted before user dropped
    # corresponding copr_chroot, and didn't have a chance to finish.
    op.execute("""
    update build_chroot
        set status = 2
    from build where
        build_chroot.build_id = build.id and
        build_chroot.status = 4 and
        build.canceled != true and
        build_chroot.copr_chroot_id is null
    """)


def downgrade():
    """ nothing needed """
