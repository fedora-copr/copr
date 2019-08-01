"""
on delete cascade for table build

Revision ID: 3cba3ffe2836
Revises: 55a07cb7bd68
Create Date: 2019-08-05 10:36:41.354582
"""

import sqlalchemy as sa
from alembic import op


revision = '3cba3ffe2836'
down_revision = '55a07cb7bd68'


def upgrade():
    op.drop_constraint('build_chroot_build_id_fkey', 'build_chroot', type_='foreignkey')
    op.create_foreign_key('build_chroot_build_id_fkey', 'build_chroot', 'build', ['build_id'], ['id'], ondelete='CASCADE')


def downgrade():
    op.drop_constraint('build_chroot_build_id_fkey', 'build_chroot', type_='foreignkey')
    op.create_foreign_key('build_chroot_build_id_fkey', 'build_chroot', 'build', ['build_id'], ['id'])
