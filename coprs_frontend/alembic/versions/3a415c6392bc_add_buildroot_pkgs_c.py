"""add buildroot_pkgs column

Revision ID: 3a415c6392bc
Revises: 52e53e7b413e
Create Date: 2013-11-28 15:46:24.860025

"""

# revision identifiers, used by Alembic.
revision = '3a415c6392bc'
down_revision = '52e53e7b413e'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('copr_chroot', sa.Column('buildroot_pkgs', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('copr_chroot', 'buildroot_pkgs')
