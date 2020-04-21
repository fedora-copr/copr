"""Change module version to bigint

Revision ID: 1f94b22f70a1
Revises: f61a5c930abf
Create Date: 2017-12-29 22:22:09.256634

"""

# revision identifiers, used by Alembic.
revision = '1f94b22f70a1'
down_revision = 'f61a5c930abf'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('module', 'version', existing_type=sa.Integer(), type_=sa.BigInteger())


def downgrade():
    op.alter_column('module', 'version', existing_type=sa.BigInteger(), type_=sa.Integer())
