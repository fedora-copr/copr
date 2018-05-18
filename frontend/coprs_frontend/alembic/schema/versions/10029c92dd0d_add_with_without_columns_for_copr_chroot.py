"""add with/without columns for copr chroot

Revision ID: 10029c92dd0d
Revises: 24e9054d4155
Create Date: 2018-05-18 18:21:53.850207

"""

# revision identifiers, used by Alembic.
revision = '10029c92dd0d'
down_revision = '24e9054d4155'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('copr_chroot', sa.Column('with_opts', sa.Text(), nullable=False, server_default=''))
    op.add_column('copr_chroot', sa.Column('without_opts', sa.Text(), nullable=False, server_default=''))


def downgrade():
    op.drop_column('copr_chroot', 'with_opts')
    op.drop_column('copr_chroot', 'without_opts')
