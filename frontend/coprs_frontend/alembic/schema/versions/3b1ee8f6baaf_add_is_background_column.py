"""Add is_background column

Revision ID: 3b1ee8f6baaf
Revises: 32fa3f232c34
Create Date: 2016-06-13 11:05:00.424325

"""

# revision identifiers, used by Alembic.
revision = '3b1ee8f6baaf'
down_revision = '32fa3f232c34'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('build', sa.Column('is_background', sa.Boolean(), server_default='0', nullable=False))


def downgrade():
    op.drop_column('build', 'is_background')
