"""
MockChroot.tags property

Revision ID: 58f7510f0fae
Revises: 55d1e8962a93
Create Date: 2022-01-10 13:36:40.330707
"""

import sqlalchemy as sa
from alembic import op


revision = '58f7510f0fae'
down_revision = '55d1e8962a93'

def upgrade():
    op.add_column('mock_chroot', sa.Column('tags_raw', sa.String(length=50), nullable=True))

def downgrade():
    op.drop_column('mock_chroot', 'tags_raw')
