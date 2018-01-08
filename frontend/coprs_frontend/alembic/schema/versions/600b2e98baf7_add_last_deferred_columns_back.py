"""add last_deferred columns back

Revision ID: 600b2e98baf7
Revises: 4edb1ca2a13f
Create Date: 2018-01-06 18:16:18.188960

"""

# revision identifiers, used by Alembic.
revision = '600b2e98baf7'
down_revision = '4edb1ca2a13f'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('build', sa.Column('last_deferred', sa.Integer(), nullable=True))
    op.add_column('build_chroot', sa.Column('last_deferred', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('build', 'last_deferred')
    op.drop_column('build_chroot', 'last_deferred')
