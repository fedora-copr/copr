"""add build requires to build_chroot

Revision ID: 227f6bf8f10b
Revises: cab566cc7dfb
Create Date: 2017-08-05 20:26:41.288965

"""

# revision identifiers, used by Alembic.
revision = '227f6bf8f10b'
down_revision = 'cab566cc7dfb'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('build_chroot', sa.Column('build_requires', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('build_chroot', 'build_requires')
