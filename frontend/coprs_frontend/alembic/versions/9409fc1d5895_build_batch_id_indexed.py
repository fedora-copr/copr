"""
Build.batch_id indexed

Revision ID: 9409fc1d5895
Revises: 58f7510f0fae
Create Date: 2022-02-15 14:38:52.680231
"""

from alembic import op


revision = '9409fc1d5895'
down_revision = '58f7510f0fae'

def upgrade():
    op.create_index(op.f('ix_build_batch_id'), 'build', ['batch_id'], unique=False)

def downgrade():
    op.drop_index(op.f('ix_build_batch_id'), table_name='build')
