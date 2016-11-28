"""add auto_prune attribute for project

Revision ID: 412c2c8d9da
Revises: 414a86b37a0f
Create Date: 2016-11-14 10:33:03.299810

"""

# revision identifiers, used by Alembic.
revision = '412c2c8d9da'
down_revision = '414a86b37a0f'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('copr', sa.Column('auto_prune', sa.Boolean(), nullable=False, server_default='t'))


def downgrade():
    op.drop_column('copr', 'auto_prune')
