"""drop Copr.build_count

Revision ID: 4837ad1d96ea
Revises: 294405dfc7c0
Create Date: 2014-01-20 17:05:20.917522

"""

# revision identifiers, used by Alembic.
revision = '4837ad1d96ea'
down_revision = '294405dfc7c0'

from alembic import op
import sqlalchemy as sa


def upgrade():
    """ Drop 'build_count' colum from copr table. """
    op.drop_column('copr', 'build_count')


def downgrade():
    """ Add 'build_count' colum to copr table. """
    op.add_column('copr', sa.Column('build_count', sa.Integer(default=0)))
