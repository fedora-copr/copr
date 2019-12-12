"""
add indexes to actions

Revision ID: a8ef299dcac8
Revises: cb928c34d36c
Create Date: 2020-01-06 14:04:30.362083
"""

import sqlalchemy as sa
from alembic import op


revision = 'a8ef299dcac8'
down_revision = 'cb928c34d36c'

def upgrade():
    op.create_index(op.f('ix_action_created_on'), 'action', ['created_on'], unique=False)
    op.create_index(op.f('ix_action_ended_on'), 'action', ['ended_on'], unique=False)

def downgrade():
    op.drop_index(op.f('ix_action_ended_on'), table_name='action')
    op.drop_index(op.f('ix_action_created_on'), table_name='action')
