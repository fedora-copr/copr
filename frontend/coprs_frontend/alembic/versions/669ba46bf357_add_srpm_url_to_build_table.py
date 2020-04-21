"""add srpm url to build table

Revision ID: 669ba46bf357
Revises: 3d89a66848c5
Create Date: 2017-09-04 14:07:47.825225

"""

# revision identifiers, used by Alembic.
revision = '669ba46bf357'
down_revision = '3d89a66848c5'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('build', sa.Column('srpm_url', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('build', 'srpm_url')
