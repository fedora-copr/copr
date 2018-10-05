"""
package.chroot_blacklist

Revision ID: 51716ab39d37
Revises: c28451aaed50
Create Date: 2018-10-04 21:24:41.498242
"""

# revision identifiers, used by Alembic.
revision = '51716ab39d37'
down_revision = 'c28451aaed50'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('package', sa.Column('chroot_blacklist_raw', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('package', 'chroot_blacklist_raw')
