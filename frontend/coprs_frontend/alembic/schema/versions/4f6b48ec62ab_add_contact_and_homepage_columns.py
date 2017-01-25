"""add contact and homepage columns

Revision ID: 4f6b48ec62ab
Revises: 57be43049e9b
Create Date: 2015-07-13 14:54:26.713819

"""

# revision identifiers, used by Alembic.
revision = '4f6b48ec62ab'
down_revision = '57be43049e9b'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(u'copr', sa.Column('contact', sa.Text, nullable=True))
    op.add_column(u'copr', sa.Column('homepage', sa.Text, nullable=True))


def downgrade():
    op.drop_column(u'copr', 'contact')
    op.drop_column(u'copr', 'homepage')
