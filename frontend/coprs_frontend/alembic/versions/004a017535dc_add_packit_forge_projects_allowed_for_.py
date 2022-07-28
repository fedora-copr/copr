"""
add packit_forge_projects_allowed for Copr projects

Revision ID: 004a017535dc
Revises: 484e28958b27
Create Date: 2022-07-28 12:20:31.777050
"""

import sqlalchemy as sa
from alembic import op


revision = '004a017535dc'
down_revision = '484e28958b27'


def upgrade():
    op.add_column('copr', sa.Column('packit_forge_projects_allowed', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('copr', 'packit_forge_projects_allowed')
