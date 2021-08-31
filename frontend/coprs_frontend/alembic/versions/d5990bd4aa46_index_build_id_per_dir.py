"""
Provide index for Build: id.desc() + copr_dir_id

Revision ID: d5990bd4aa46
Revises: 45d0515bdc3f
Create Date: 2021-08-31 14:43:28.534127
"""

import sqlalchemy as sa
from alembic import op


revision = 'd5990bd4aa46'
down_revision = '45d0515bdc3f'

def upgrade():
    op.create_index('build_id_desc_per_copr_dir', 'build',
                    [sa.text('id DESC'), 'copr_dir_id'], unique=False)

def downgrade():
    op.drop_index('build_id_desc_per_copr_dir', table_name='build')
