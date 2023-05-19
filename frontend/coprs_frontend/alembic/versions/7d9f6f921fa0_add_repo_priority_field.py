"""
Add repo priority field

Revision ID: 7d9f6f921fa0
Revises: ba6ac0936bfb
Create Date: 2023-05-25 11:05:39.877208
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7d9f6f921fa0'
down_revision = 'ba6ac0936bfb'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('copr', sa.Column('repo_priority', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('copr', 'repo_priority')
