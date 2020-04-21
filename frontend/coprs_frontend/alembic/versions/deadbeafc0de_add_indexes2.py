"""add indexes2

Revision ID: deadbeafc0de_add_indexes.py
Revises: 10029c92dd0d
Create Date: 2019-01-14 14:43:00.000000

"""

# revision identifiers, used by Alembic.
revision = 'deadbeafc0de'
down_revision = 'deaddeadc0de'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_index('build_package_idx', 'build', ['package_id'], unique=False)
    op.create_index('copr_user_id_idx', 'copr', ['user_id'], unique=False)
    op.create_index('copr_name_group_id_idx', 'copr', ['name', 'group_id'], unique=False)
    op.create_index('package_copr_id_idx', 'package', ['copr_id'], unique=False)
    op.create_index('build_user_id_idx', 'build', ['user_id'], unique=False)


def downgrade():
    op.drop_index('build_user_id_idx', table_name='build')
    op.drop_index('package_copr_id_idx', table_name='package')
    op.drop_index('copr_name_group_id_idx', table_name='copr')
    op.drop_index('copr_user_id_idx', table_name='copr')
    op.drop_index('build_package_idx', table_name='build')
