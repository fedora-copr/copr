"""change module version to bigint

Revision ID: 4c6d0a2db343
Revises: 3fdedd58ac73
Create Date: 2016-11-23 04:43:29.207158

"""

# revision identifiers, used by Alembic.
revision = '4c6d0a2db343'
down_revision = '3fdedd58ac73'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('module', 'version', existing_type=sa.Integer(), type_=sa.BigInteger())


def downgrade():
    op.alter_column('module', 'version', existing_type=sa.BigInteger(), type_=sa.Integer())
