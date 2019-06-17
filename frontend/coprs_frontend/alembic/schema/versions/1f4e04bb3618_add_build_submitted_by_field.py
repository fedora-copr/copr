"""
add build.submitted_by field

Revision ID: 1f4e04bb3618
Revises: 2d8b4722918b
Create Date: 2019-06-10 06:08:14.501770
"""

import sqlalchemy as sa
from alembic import op


revision = '1f4e04bb3618'
down_revision = '2d8b4722918b'

def upgrade():
    op.add_column('build', sa.Column('submitted_by', sa.Text(), nullable=True))

def downgrade():
    op.drop_column('build', 'submitted_by')
