"""latest_indexed_data_updated column added for copr

Revision ID: 1ea00801be9e
Revises: 1c61e5b88e45
Create Date: 2016-07-19 15:45:05.524428

"""

# revision identifiers, used by Alembic.
revision = '1ea00801be9e'
down_revision = '1c61e5b88e45'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('copr', sa.Column('latest_indexed_data_update', sa.Integer(), nullable=True))

def downgrade():
    op.drop_column('copr', 'latest_indexed_data_update')
