"""
Add composite index for BuildChrootResult search

Revision ID: 3c1f3f1b1b6a
Revises: 091ed798e555
Create Date: 2026-02-12 00:00:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = '3c1f3f1b1b6a'
down_revision = '091ed798e555'
branch_labels = None
depends_on = None


INDEX_NAME = "build_chroot_result_name_version_release_arch_epoch_idx"
TABLE_NAME = "build_chroot_result"


def upgrade():
    op.create_index(
        INDEX_NAME,
        TABLE_NAME,
        ["name", "version", "release", "arch", "epoch"],
        unique=False,
    )


def downgrade():
    op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
