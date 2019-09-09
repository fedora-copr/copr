"""
add comment to mock_chroot table

Revision ID: 6800e08934eb
Revises: 12abab545d7a
Create Date: 2019-07-30 08:49:53.205823
"""

import sqlalchemy as sa
from alembic import op


revision = '6800e08934eb'
down_revision = '12abab545d7a'

def upgrade():
    op.add_column('mock_chroot', sa.Column('comment', sa.Text, nullable=True))

def downgrade():
    op.drop_column('mock_chroot', 'comment')
