"""
Remove unused module_md_name and module_md_zlib columns

Revision ID: 2d8b4722918b
Revises: 8ae65946df53
Create Date: 2019-05-05 17:42:00.875012
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '2d8b4722918b'
down_revision = '8ae65946df53'

def upgrade():
    op.drop_column('copr_chroot', 'module_md_name')
    op.drop_column('copr_chroot', 'module_md_zlib')

def downgrade():
    op.add_column('copr_chroot', sa.Column('module_md_zlib', postgresql.BYTEA(), autoincrement=False, nullable=True))
    op.add_column('copr_chroot', sa.Column('module_md_name', sa.VARCHAR(length=127), autoincrement=False, nullable=True))
