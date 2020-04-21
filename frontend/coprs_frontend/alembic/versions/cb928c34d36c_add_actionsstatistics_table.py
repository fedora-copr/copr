"""
add ActionsStatistics table

Revision ID: cb928c34d36c
Revises: 2db1d0557b06
Create Date: 2019-12-06 09:33:12.210295
"""

import sqlalchemy as sa
from alembic import op


revision = 'cb928c34d36c'
down_revision = '2db1d0557b06'

def upgrade():
    op.create_table('actions_statistics',
    sa.Column('time', sa.Integer(), nullable=False),
    sa.Column('stat_type', sa.Text(), nullable=False),
    sa.Column('waiting', sa.Integer(), nullable=True),
    sa.Column('success', sa.Integer(), nullable=True),
    sa.Column('failed', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('time', 'stat_type')
    )

def downgrade():
    op.drop_table('actions_statistics')
