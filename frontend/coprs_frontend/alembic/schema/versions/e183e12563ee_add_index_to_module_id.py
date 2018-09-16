"""Add index to module_id

Revision ID: e183e12563ee
Revises: 1f94b22f70a1
Create Date: 2018-01-07 11:03:29.885276

"""

# revision identifiers, used by Alembic.
revision = 'e183e12563ee'
down_revision = '1f94b22f70a1'

from alembic import op


def upgrade():
    op.create_index(op.f('ix_build_module_id'), 'build', ['module_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_build_module_id'), table_name='build')
