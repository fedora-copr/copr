"""make new prio columns

Revision ID: 7bb0c7762df0
Revises: 512ff2b9eb6c
Create Date: 2017-10-23 15:40:53.205814

"""

# revision identifiers, used by Alembic.
revision = '7bb0c7762df0'
down_revision = '512ff2b9eb6c'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_column('build_chroot', 'last_deferred')
    op.add_column('build_chroot', sa.Column('priority', sa.BigInteger(), server_default='0',nullable=False))
    op.add_column('build', sa.Column('priority', sa.BigInteger(), server_default='0', nullable=False))


def downgrade():
    op.add_column('build_chroot', sa.Column('last_deferred', sa.Integer(), server_default='0', nullable=True))
    op.drop_column('build_chroot', 'priority')
    op.drop_column('build', 'priority')
