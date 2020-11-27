"""
isolation option for chroot

Revision ID: 8fd7c4714189
Revises: d6cbf6cd74da
Create Date: 2020-11-27 14:57:55.008281
"""

import sqlalchemy as sa
from alembic import op


revision = '8fd7c4714189'
down_revision = 'd6cbf6cd74da'


def upgrade():
    op.add_column('copr_chroot', sa.Column('isolation', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('copr_chroot', 'isolation')
