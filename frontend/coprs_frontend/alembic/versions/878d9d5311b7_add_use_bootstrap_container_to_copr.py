"""add use_bootstrap_container to copr

Revision ID: 878d9d5311b7
Revises: bf4b5dc74740
Create Date: 2017-06-13 16:52:52.703209

"""

# revision identifiers, used by Alembic.
revision = '878d9d5311b7'
down_revision = 'bf4b5dc74740'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('copr', sa.Column('use_bootstrap_container', sa.Boolean(), nullable=False, server_default='f'))


def downgrade():
    op.drop_column('copr', 'use_bootstrap_container')
