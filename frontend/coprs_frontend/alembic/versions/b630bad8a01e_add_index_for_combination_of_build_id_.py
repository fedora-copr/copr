"""
Add index for combination of build.id and build.copr_id

Revision ID: b630bad8a01e
Revises: d5990bd4aa46
Create Date: 2021-09-28 15:14:31.574563
"""

from alembic import op


revision = 'b630bad8a01e'
down_revision = 'd5990bd4aa46'


def upgrade():
    op.create_index('build_copr_id_build_id', 'build', ['copr_id', 'id'], unique=True)


def downgrade():
    op.drop_index('build_copr_id_build_id', table_name='build')
