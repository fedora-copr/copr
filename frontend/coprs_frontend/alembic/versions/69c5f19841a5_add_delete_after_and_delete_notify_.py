"""Add delete_after and delete_notify columns

Revision ID: 69c5f19841a5
Revises: c28451aaed50
Create Date: 2018-10-09 00:25:40.725051

"""

# revision identifiers, used by Alembic.
revision = '69c5f19841a5'
down_revision = '51716ab39d37'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('copr_chroot', sa.Column('delete_after', sa.DateTime(), nullable=True))
    op.add_column('copr_chroot', sa.Column('delete_notify', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('copr_chroot', 'delete_notify')
    op.drop_column('copr_chroot', 'delete_after')
