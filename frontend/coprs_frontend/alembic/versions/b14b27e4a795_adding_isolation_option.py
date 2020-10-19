"""
Adding isolation option

Revision ID: b14b27e4a795
Revises: 63db6872060f
Create Date: 2020-10-19 13:51:59.349687
"""

import sqlalchemy as sa
from alembic import op


revision = 'b14b27e4a795'
down_revision = '9b7211be5017'


def upgrade():
    op.add_column('build', sa.Column('isolation', sa.Text(), nullable=True))
    op.add_column('copr', sa.Column('isolation', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('copr', 'isolation')
    op.drop_column('build', 'isolation')
