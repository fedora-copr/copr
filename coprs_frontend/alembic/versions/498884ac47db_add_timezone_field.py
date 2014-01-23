"""add timezone field

Revision ID: 498884ac47db
Revises: 3a415c6392bc
Create Date: 2014-01-23 12:15:04.450292

"""

# revision identifiers, used by Alembic.
revision = '498884ac47db'
down_revision = '3a415c6392bc'

from alembic import op
import sqlalchemy as sa


def upgrade():
    """ Add 'data' colum to action table. """
    op.add_column('user', sa.Column('timezone', sa.String(length=50), nullable=False))


def downgrade():
    """ Drop 'data' colum from action table. """
    op.drop_column('user', 'timezone')
