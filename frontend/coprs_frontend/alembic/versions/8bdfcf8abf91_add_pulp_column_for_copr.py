"""
Add pulp column for copr

Revision ID: 8bdfcf8abf91
Create Date: 2024-05-02 09:24:11.286356
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8bdfcf8abf91'
down_revision = '41763f7a5185'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('copr', sa.Column('pulp', sa.Boolean(), server_default='0',
                                    nullable=False))


def downgrade():
    op.drop_column('copr', 'pulp')
