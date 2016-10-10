"""add unique constraint on (copr_id, name) in package table

Revision ID: 414a86b37a0f
Revises: 38f205566f20
Create Date: 2016-10-10 14:09:22.972767

"""

# revision identifiers, used by Alembic.
revision = '414a86b37a0f'
down_revision = '38f205566f20'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_unique_constraint("packages_copr_pkgname", "package", ["copr_id", "name"])


def downgrade():
    op.drop_constraint("packages_copr_pkgname", "package")
