"""
Add storage column for copr projects

Revision ID: 2d1feab6b2d8
Create Date: 2024-06-23 12:20:49.908070
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2d1feab6b2d8'
down_revision = '9fec2c962fcd'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('copr', sa.Column('storage', sa.Integer()))


def downgrade():
    op.drop_column('copr', 'storage')
