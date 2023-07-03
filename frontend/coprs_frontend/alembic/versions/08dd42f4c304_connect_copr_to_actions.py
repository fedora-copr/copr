"""
Connect Copr to Actions

Revision ID: 08dd42f4c304
Create Date: 2023-08-03 15:45:53.527538
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '08dd42f4c304'
down_revision = 'daa62cd0743d'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('action', sa.Column('copr_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_action_copr_id'), 'action', ['copr_id'], unique=False)
    op.create_foreign_key(None, 'action', 'copr', ['copr_id'], ['id'])


def downgrade():
    op.drop_constraint(None, 'action', type_='foreignkey')
    op.drop_index(op.f('ix_action_copr_id'), table_name='action')
    op.drop_column('action', 'copr_id')
