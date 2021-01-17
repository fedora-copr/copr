"""
Add deleted column for CoprChroot

Revision ID: 6866cd91c3c6
Revises: 8fd7c4714189
Create Date: 2021-01-17 20:15:33.324380
"""

import sqlalchemy as sa
from alembic import op


revision = '6866cd91c3c6'
down_revision = '1c67bc715d78'


def upgrade():
    op.add_column('copr_chroot', sa.Column('deleted', sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column('copr_chroot', 'deleted')
