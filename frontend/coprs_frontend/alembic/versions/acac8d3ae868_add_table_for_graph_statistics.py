"""add table for graph statistics

Revision ID: acac8d3ae868
Revises: 10029c92dd0d
Create Date: 2018-06-28 11:39:43.913783

"""

# revision identifiers, used by Alembic.
revision = 'acac8d3ae868'
down_revision = '10029c92dd0d'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('builds_statistics',
    sa.Column('time', sa.Integer(), nullable=False),
    sa.Column('stat_type', sa.Text(), nullable=False),
    sa.Column('running', sa.Integer(), nullable=True),
    sa.Column('pending', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('time', 'stat_type')
    )
    op.create_index(op.f('ix_build_chroot_started_on'), 'build_chroot', ['started_on'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_build_chroot_started_on'), table_name='build_chroot')
    op.drop_table('builds_statistics')
    # ### end Alembic commands ###
