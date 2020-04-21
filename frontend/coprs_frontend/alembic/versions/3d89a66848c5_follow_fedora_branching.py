"""Follow Fedora branching

Revision ID: 3d89a66848c5
Revises: 227f6bf8f10b
Create Date: 2017-08-09 15:58:52.131456

"""

# revision identifiers, used by Alembic.
revision = '3d89a66848c5'
down_revision = '227f6bf8f10b'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('copr', sa.Column('follow_fedora_branching', sa.Boolean(), nullable=False, server_default='f'))


def downgrade():
    op.drop_column('copr', 'follow_fedora_branching')
