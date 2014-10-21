"""Copr added attribute 'auto_createrepo'

Revision ID: 1d5b5b1b27f9
Revises: 2a4242380f24
Create Date: 2014-10-21 14:32:45.062257

"""

# revision identifiers, used by Alembic.
revision = '1d5b5b1b27f9'
down_revision = '2a4242380f24'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('copr', sa.Column('auto_createrepo', sa.Boolean(),
                  default=True, server_default="true", nullable=False))


def downgrade():
    op.drop_column('copr', 'auto_createrepo')

