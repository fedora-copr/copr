"""Add blocked_by column for batch

Revision ID: 8ae65946df53
Revises: b64659389c54
Create Date: 2019-03-27 18:38:03.758974

"""

# revision identifiers, used by Alembic.
revision = '8ae65946df53'
down_revision = '9bc8681ed275'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('batch', sa.Column('blocked_by_id', sa.Integer(), nullable=True))
    op.create_foreign_key('batch_blocked_by_id_fkey', 'batch', 'batch', ['blocked_by_id'], ['id'])


def downgrade():
    op.drop_constraint('batch_blocked_by_id_fkey', 'batch', type_='foreignkey')
    op.drop_column('batch', 'blocked_by_id')
