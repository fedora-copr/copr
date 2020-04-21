"""Add build to module relation

Revision ID: 3b0851cb25fc
Revises: 7bb0c7762df0
Create Date: 2017-12-27 13:46:07.774167

"""

# revision identifiers, used by Alembic.
revision = '3b0851cb25fc'
down_revision = '7bb0c7762df0'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('build', sa.Column('module_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'build', 'module', ['module_id'], ['id'])


def downgrade():
    op.drop_constraint(None, 'build', type_='foreignkey')
    op.drop_column('build', 'module_id')
