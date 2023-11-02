"""
Add ssh_public_keys column

Revision ID: 41763f7a5185
Create Date: 2023-11-02 09:30:57.246569
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '41763f7a5185'
down_revision = 'ec3528516b0c'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('build', sa.Column('ssh_public_keys', sa.Text()))


def downgrade():
    op.drop_column('build', 'ssh_public_keys')
