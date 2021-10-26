"""
Add index for BuildChrootResult.build_id

Revision ID: 55d1e8962a93
Revises: 33a73ed44f83
Create Date: 2021-10-26 13:25:28.194683
"""

from alembic import op


revision = '55d1e8962a93'
down_revision = '33a73ed44f83'

def upgrade():
    op.create_index(op.f('ix_build_chroot_result_build_chroot_id'),
                    'build_chroot_result', ['build_chroot_id'], unique=False)

def downgrade():
    op.drop_index(op.f('ix_build_chroot_result_build_chroot_id'),
                  table_name='build_chroot_result')
