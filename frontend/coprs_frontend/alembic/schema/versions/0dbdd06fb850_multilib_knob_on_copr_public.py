"""
multilib knob on copr_public

Revision ID: 0dbdd06fb850
Revises: 12abab545d7a
Create Date: 2019-08-20 22:41:50.747899
"""

import sqlalchemy as sa
from alembic import op


revision = '0dbdd06fb850'
down_revision = '6800e08934eb'

def upgrade():
    op.add_column('copr', sa.Column('multilib', sa.Boolean(), server_default='0', nullable=False))

def downgrade():
    op.drop_column('copr', 'multilib')
