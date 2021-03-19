"""
add column appstream

Revision ID: 2318cc31444e
Revises: efec6b1aa9a2
Create Date: 2021-04-28 14:07:25.439393
"""

import sqlalchemy as sa
from alembic import op


revision = '2318cc31444e'
down_revision = 'efec6b1aa9a2'


def upgrade():
    op.add_column('copr', sa.Column('appstream', sa.Boolean(), server_default='1', nullable=False))


def downgrade():
    op.drop_column('copr', 'appstream')
