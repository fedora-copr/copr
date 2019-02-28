"""add column final_prunerepo_done to mock_chroot table

Revision ID: b64659389c54
Revises: ca76b7902c2f
Create Date: 2019-02-28 11:57:48.674072

"""

# revision identifiers, used by Alembic.
revision = 'b64659389c54'
down_revision = 'ca76b7902c2f'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('mock_chroot', sa.Column('final_prunerepo_done', sa.Boolean, nullable=False, server_default='0'))


def downgrade():
    op.drop_column('mock_chroot', 'final_prunerepo_done')
