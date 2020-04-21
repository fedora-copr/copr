"""
new column resubmitted_from_id

Revision ID: 745250baedaf
Revises: 0dbdd06fb850
Create Date: 2019-11-11 11:15:05.399008
"""

import sqlalchemy as sa
from alembic import op


revision = '745250baedaf'
down_revision = '0dbdd06fb850'

def upgrade():
    op.add_column('build', sa.Column('resubmitted_from_id', sa.Integer(), nullable=True))

def downgrade():
    op.drop_column('build', 'resubmitted_from_id')
