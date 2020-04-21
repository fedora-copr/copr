"""
Added index for main in copr_dir

Revision ID: 12abab545d7a
Revises: 3cba3ffe2836
Create Date: 2019-08-19 08:18:02.561158
"""

import sqlalchemy as sa
from alembic import op


revision = '12abab545d7a'
down_revision = '3cba3ffe2836'


def upgrade():
    op.create_index(op.f('ix_copr_dir_main'), 'copr_dir', ['main'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_copr_dir_main'), table_name='copr_dir')
