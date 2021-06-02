"""
index CoprChroot.deleted

Revision ID: 8ea94673d6ee
Revises: 2318cc31444e
Create Date: 2021-06-02 07:19:47.605140
"""

from alembic import op


revision = '8ea94673d6ee'
down_revision = '2318cc31444e'

def upgrade():
    op.create_index(op.f('ix_copr_chroot_deleted'), 'copr_chroot', ['deleted'], unique=False)

def downgrade():
    op.drop_index(op.f('ix_copr_chroot_deleted'), table_name='copr_chroot')
