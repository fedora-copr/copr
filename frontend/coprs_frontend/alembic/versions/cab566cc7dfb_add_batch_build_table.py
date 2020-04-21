"""add batch build table

Revision ID: cab566cc7dfb
Revises: 878d9d5311b7
Create Date: 2017-08-05 20:14:56.817954

"""

# revision identifiers, used by Alembic.
revision = 'cab566cc7dfb'
down_revision = '878d9d5311b7'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('batch',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.add_column('build',
        sa.Column('batch_id', sa.Integer(), sa.ForeignKey('batch.id'), nullable=True)
    )


def downgrade():
    op.drop_table('batch')
    op.drop_column('build', 'batch_id')
