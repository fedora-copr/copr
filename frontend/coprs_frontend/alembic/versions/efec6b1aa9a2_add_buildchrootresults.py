"""
Add BuildChrootResults

Revision ID: efec6b1aa9a2
Revises: d8a1062ee4cf
Create Date: 2021-05-13 16:48:05.569521
"""

import sqlalchemy as sa
from alembic import op


revision = 'efec6b1aa9a2'
down_revision = 'd8a1062ee4cf'

def upgrade():
    op.create_table('build_chroot_result',

    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('build_chroot_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('epoch', sa.Integer(), default=0),
    sa.Column('version', sa.Text(), nullable=False),
    sa.Column('release', sa.Text(), nullable=False),
    sa.Column('arch', sa.Text(), nullable=False),

    sa.ForeignKeyConstraint(['build_chroot_id'], ['build_chroot.id'],
                            ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('build_chroot_result')
