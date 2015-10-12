"""Add openid_group column

Revision ID: 3ec22e1db75a
Revises: 3f4966a9cc0
Create Date: 2015-10-09 07:56:41.303179

"""

# revision identifiers, used by Alembic.
revision = '3ec22e1db75a'
down_revision = '3f4966a9cc0'

from alembic import op
import sqlalchemy as sa
from coprs.helpers import JSONEncodedDict

def upgrade():
    op.add_column('user', sa.Column('openid_groups', JSONEncodedDict(), nullable=True))


def downgrade():
    op.drop_column('user', 'openid_groups')
