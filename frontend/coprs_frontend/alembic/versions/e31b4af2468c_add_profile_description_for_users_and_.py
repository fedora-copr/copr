"""
Add profile description for users and groups

Revision ID: e31b4af2468c
Revises: 3c1f3f1b1b6a
Create Date: 2026-02-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e31b4af2468c'
down_revision = '3c1f3f1b1b6a'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('profile_description', sa.Text(), nullable=True))
    op.add_column('group', sa.Column('profile_description', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('group', 'profile_description')
    op.drop_column('user', 'profile_description')
