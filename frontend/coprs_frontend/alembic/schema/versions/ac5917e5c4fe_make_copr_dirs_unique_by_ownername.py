"""make copr_dirs unique by ownername

Revision ID: ac5917e5c4fe
Revises: 887cbbd6575e
Create Date: 2018-07-19 11:45:57.228628

"""

# revision identifiers, used by Alembic.
revision = 'ac5917e5c4fe'
down_revision = '887cbbd6575e'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('copr_dir', sa.Column('ownername', sa.Text(), nullable=False))
    op.create_index(op.f('ix_copr_dir_ownername'), 'copr_dir', ['ownername'], unique=False)
    op.create_unique_constraint('ownername_copr_dir_uniq', 'copr_dir', ['ownername', 'name'])
    op.drop_constraint(u'copr_dir_copr_id_name_uniq', 'copr_dir', type_='unique')


def downgrade():
    op.create_unique_constraint(u'copr_dir_copr_id_name_uniq', 'copr_dir', ['copr_id', 'name'])
    op.drop_constraint('ownername_copr_dir_uniq', 'copr_dir', type_='unique')
    op.drop_index(op.f('ix_copr_dir_ownername'), table_name='copr_dir')
    op.drop_column('copr_dir', 'ownername')
