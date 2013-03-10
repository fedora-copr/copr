"""Add a api_login field to user

Revision ID: 2a75f0a06d90
Revises: 544873aa3ba1
Create Date: 2013-03-10 10:01:16.820499

"""

# revision identifiers, used by Alembic.
revision = '2a75f0a06d90'
down_revision = '544873aa3ba1'

from alembic import op
import sqlalchemy as sa


def upgrade():
    """ Add the colum 'api_login' to the table user. """
    op.add_column('user', sa.Column('api_login', sa.String(40),
        nullable=False, server_default='default_token'))


def downgrade():
    """ Drop the column 'api_login' from the table user. """
    op.drop_column('user', 'api_login')
