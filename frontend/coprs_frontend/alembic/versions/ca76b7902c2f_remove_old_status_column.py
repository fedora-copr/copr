"""remove old_status column

Revision ID: ca76b7902c2f
Revises: code4beaf000
Create Date: 2019-03-05 08:47:31.519455

"""

# revision identifiers, used by Alembic.
revision = 'ca76b7902c2f'
down_revision = 'code4beaf000'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_column('package', 'old_status')


def downgrade():
    op.add_column('package', sa.Column('old_status', sa.Integer(), nullable=True))
