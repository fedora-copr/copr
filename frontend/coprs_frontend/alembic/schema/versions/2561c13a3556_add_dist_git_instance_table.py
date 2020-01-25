"""
add dist_git_instance table

Revision ID: 2561c13a3556
Revises: d230af5e05d8
Create Date: 2020-01-30 14:49:07.698008
"""

import sqlalchemy as sa
from alembic import op


revision = '2561c13a3556'
down_revision = 'd230af5e05d8'

def upgrade():
    new_table = op.create_table('dist_git_instance',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.Column('clone_url', sa.String(length=100), nullable=False),
    sa.Column('clone_package_uri', sa.String(length=100), nullable=False),
    sa.Column('priority', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.bulk_insert(new_table, [{
        'name': 'fedora',
        'clone_url': 'https://src.fedoraproject.org',
        'clone_package_uri': 'rpms/{pkgname}.git',
        'priority': 100,
    }])

def downgrade():
    op.drop_table('dist_git_instance')
