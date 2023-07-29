"""
add unique constraint to fas_group

Revision ID: daa62cd0743d
Revises: ba6ac0936bfb
Create Date: 2023-08-01 09:52:01.522171
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = 'daa62cd0743d'
down_revision = '7d9f6f921fa0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(None, 'group', ['fas_name'])


def downgrade():
    op.drop_constraint(None, 'group', type_='unique')
