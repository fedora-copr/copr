"""remove_priority_columns

Revision ID: 4edb1ca2a13f
Revises: e183e12563ee
Create Date: 2018-01-01 16:34:13.196247

"""

# revision identifiers, used by Alembic.
revision = '4edb1ca2a13f'
down_revision = 'e183e12563ee'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_column('build_chroot', 'priority')
    op.drop_column('build', 'priority')


def downgrade():
    op.add_column('build_chroot', sa.Column('priority', sa.BigInteger(), server_default='0',nullable=False))
    op.add_column('build', sa.Column('priority', sa.BigInteger(), server_default='0', nullable=False))
