"""add indexes

Revision ID: deaddeadc0de_add_indexes.py
Revises: 10029c92dd0d
Create Date: 2018-06-27 14:43:00.000000

"""

# revision identifiers, used by Alembic.
revision = 'deaddeadc0de'
down_revision = '8bf844cc7135'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_index('build_copr_id', 'build', ['copr_id'], unique=False)
    op.create_index('build_chroot_status_started_on_idx', 'build_chroot', ['status', 'started_on'], unique=False)
    ### end Alembic commands ###


def downgrade():
    op.drop_index('build_status_started_on_idx', table_name='build')
    op.drop_index('build_copr_id', table_name='build')
