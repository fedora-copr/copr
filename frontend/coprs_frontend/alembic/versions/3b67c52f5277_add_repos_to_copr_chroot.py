"""add repos to copr_chroot

Revision ID: 3b67c52f5277
Revises: 4c6d0a2db343
Create Date: 2016-11-24 12:06:34.092195

"""

# revision identifiers, used by Alembic.
revision = '3b67c52f5277'
down_revision = 'dabab11132c1'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(u'copr_chroot', sa.Column('repos', sa.Text(), nullable=False, server_default=''))


def downgrade():
    op.drop_column(u'copr_chroot', 'repos')
