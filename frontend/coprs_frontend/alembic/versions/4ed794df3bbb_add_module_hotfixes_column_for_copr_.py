"""
Add module_hotfixes column for copr table

Revision ID: 4ed794df3bbb
Revises: 0dbdd06fb850
Create Date: 2019-11-07 10:01:24.496244
"""

import sqlalchemy as sa
from alembic import op


revision = '4ed794df3bbb'
down_revision = '745250baedaf'

def upgrade():
    op.add_column('copr', sa.Column('module_hotfixes', sa.Boolean(), server_default='0', nullable=False))

def downgrade():
    op.drop_column('copr', 'module_hotfixes')
