"""
add runtime dependencies to copr

Revision ID: 6f83ea2ba416
Revises: 6d0a02dc7de4
Create Date: 2020-02-04 10:39:20.522370
"""

import sqlalchemy as sa
from alembic import op


revision = '6f83ea2ba416'
down_revision = '6d0a02dc7de4'


def upgrade():
    op.add_column('copr', sa.Column('runtime_dependencies', sa.Text()))


def downgrade():
    op.drop_column('copr', 'runtime_dependencies')
