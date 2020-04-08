"""
Add priority column for actions

Revision ID: 58eab04e5afc
Revises: 67ba91dda3e3
Create Date: 2020-04-07 11:02:52.871921
"""

import sqlalchemy as sa
from alembic import op


revision = '58eab04e5afc'
down_revision = '67ba91dda3e3'

def upgrade():
    op.add_column('action', sa.Column('priority', sa.Integer(), nullable=True))

def downgrade():
    op.drop_column('action', 'priority')
