"""
Add reviewed_outdated_chroot table

Revision ID: 9b7211be5017
Revises: de903581465c
Create Date: 2020-10-08 11:27:27.588111
"""

import sqlalchemy as sa
from alembic import op


revision = '9b7211be5017'
down_revision = '63db6872060f'

def upgrade():
    op.create_table('reviewed_outdated_chroot',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('copr_chroot_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['copr_chroot_id'], ['copr_chroot.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reviewed_outdated_chroot_user_id'), 'reviewed_outdated_chroot', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_reviewed_outdated_chroot_user_id'), table_name='reviewed_outdated_chroot')
    op.drop_table('reviewed_outdated_chroot')
