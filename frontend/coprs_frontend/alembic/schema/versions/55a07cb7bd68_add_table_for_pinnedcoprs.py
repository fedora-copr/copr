"""
Add table for PinnedCoprs

Revision ID: 55a07cb7bd68
Revises: 2d8b4722918b
Create Date: 2019-06-24 22:18:20.411614
"""

import sqlalchemy as sa
from alembic import op


revision = '55a07cb7bd68'
down_revision = '1f4e04bb3618'


def upgrade():
    op.create_table('pinned_coprs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),

        sa.Column('copr_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('group_id', sa.Integer(), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False),

        sa.ForeignKeyConstraint(['copr_id'], ['copr.id'], ),
        sa.ForeignKeyConstraint(['group_id'], ['group.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    )
    op.create_index(op.f('ix_pinned_coprs_user_id'), 'pinned_coprs', ['user_id'], unique=False),
    op.create_index(op.f('ix_pinned_coprs_group_id'), 'pinned_coprs', ['group_id'], unique=False),


def downgrade():
    op.drop_table('pinned_coprs')
