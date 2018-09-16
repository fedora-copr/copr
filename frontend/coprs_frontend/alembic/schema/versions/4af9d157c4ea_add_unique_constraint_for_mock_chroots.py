"""add unique constraint for mock chroots

Revision ID: 4af9d157c4ea
Revises: 3b67c52f5277
Create Date: 2017-01-20 16:44:30.473253

"""

# revision identifiers, used by Alembic.
revision = '4af9d157c4ea'
down_revision = '3b67c52f5277'

from alembic import op

def upgrade():
    op.create_unique_constraint('mock_chroot_uniq', 'mock_chroot', ['os_release', 'os_version', 'arch'])

def downgrade():
    op.drop_constraint('mock_chroot_uniq', 'mock_chroot', type_='unique')
