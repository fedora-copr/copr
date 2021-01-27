"""
Add fedora_review column for projects

Revision ID: 1c67bc715d78
Revises: 8fd7c4714189
Create Date: 2021-01-26 22:04:22.633733
"""

import sqlalchemy as sa
from alembic import op


revision = '1c67bc715d78'
down_revision = '8fd7c4714189'


def upgrade():
    op.add_column('copr', sa.Column('fedora_review', sa.Boolean(), server_default='0', nullable=False))


def downgrade():
    op.drop_column('copr', 'fedora_review')
