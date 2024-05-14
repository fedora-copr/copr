"""
record last copr_chroot build, allow marking Rawhide as rolling
Create Date: 2024-05-13 08:56:31.557843
"""

import time
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

revision = 'd23f84f87130'
down_revision = '2d1feab6b2d8'

def upgrade():
    op.add_column('mock_chroot', sa.Column('rolling', sa.Boolean(), nullable=True))
    op.add_column('copr_chroot', sa.Column('last_build_timestamp', sa.Integer(), nullable=True))
    conn = op.get_bind()
    conn.execute(
        text("update copr_chroot set last_build_timestamp = :start_stamp;"),
        {"start_stamp": int(time.time())},
    )
    op.create_index('copr_chroot_rolling_last_build_idx', 'copr_chroot',
                    ['mock_chroot_id', 'last_build_timestamp', 'delete_after'],
                    unique=False)


def downgrade():
    op.drop_index('copr_chroot_rolling_last_build_idx', table_name='copr_chroot')
    op.drop_column('copr_chroot', 'last_build_timestamp')
    op.drop_column('mock_chroot', 'rolling')
