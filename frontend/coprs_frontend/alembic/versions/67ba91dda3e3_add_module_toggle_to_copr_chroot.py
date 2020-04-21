"""
add module_toggle to copr_chroot

Revision ID: 67ba91dda3e3
Revises: 2561c13a3556
Create Date: 2020-01-17 10:48:22.092706
"""

import sqlalchemy as sa
from alembic import op


revision = '67ba91dda3e3'
down_revision = '2561c13a3556'

def upgrade():
    op.add_column('copr_chroot', sa.Column('module_toggle', sa.Text(), nullable=True))

def downgrade():
    op.drop_column('copr_chroot', 'module_toggle')
