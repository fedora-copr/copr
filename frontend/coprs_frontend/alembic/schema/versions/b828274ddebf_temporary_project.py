"""
temporary project

Revision ID: b828274ddebf
Revises: b64659389c54
Create Date: 2019-04-05 11:55:08.004627
"""

import sqlalchemy as sa
from alembic import op

revision = 'b828274ddebf'
down_revision = 'b8a8a1345ed9'

def upgrade():
    op.add_column('copr', sa.Column('delete_after', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_copr_delete_after'), 'copr', ['delete_after'], unique=False)

def downgrade():
    op.drop_index(op.f('ix_copr_delete_after'), table_name='copr')
    op.drop_column('copr', 'delete_after')
