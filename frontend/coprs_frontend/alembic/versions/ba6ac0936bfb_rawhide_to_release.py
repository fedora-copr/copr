"""
rawhide_to_release index

Revision ID: ba6ac0936bfb
Revises: bc29f080b915
Create Date: 2023-02-06 21:53:57.473328
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = 'ba6ac0936bfb'
down_revision = 'bc29f080b915'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('build_chroot_rawhide_to_release', 'build_chroot',
                    ['mock_chroot_id', 'status', 'build_id'], unique=False)


def downgrade():
    op.drop_index('build_chroot_rawhide_to_release', table_name='build_chroot')
