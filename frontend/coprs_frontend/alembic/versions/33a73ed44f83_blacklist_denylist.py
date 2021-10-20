"""
blacklist => denylist

Revision ID: 33a73ed44f83
Revises: b630bad8a01e
Create Date: 2021-10-20 21:16:15.229677
"""

from alembic import op

revision = '33a73ed44f83'
down_revision = 'b630bad8a01e'

def upgrade():
    op.alter_column('package', 'chroot_blacklist_raw',
                    new_column_name='chroot_denylist_raw')

def downgrade():
    op.alter_column('package', 'chroot_denylist_raw',
                    new_column_name='chroot_blacklist_raw')
