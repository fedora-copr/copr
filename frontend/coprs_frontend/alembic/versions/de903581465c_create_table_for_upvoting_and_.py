"""
Create table for upvoting and downvoting projects

Revision ID: de903581465c
Revises: 484a1d4dd424
Create Date: 2020-07-26 19:36:51.199148
"""

import sqlalchemy as sa
from alembic import op


revision = 'de903581465c'
down_revision = '484a1d4dd424'

def upgrade():
    op.create_table(
        'copr_score',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('copr_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['copr_id'], ['copr.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_copr_score_copr_id'), 'copr_score', ['copr_id'], unique=False)
    op.create_unique_constraint('copr_score_copr_id_user_id_uniq', 'copr_score', ['copr_id', 'user_id'])


def downgrade():
    op.drop_constraint('copr_score_copr_id_user_id_uniq', 'copr_score', type_='unique')
    op.drop_index(op.f('ix_copr_score_copr_id'), table_name='copr_score')
    op.drop_table('copr_score')
