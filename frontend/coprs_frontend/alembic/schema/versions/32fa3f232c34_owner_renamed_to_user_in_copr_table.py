"""Owner renamed to User in copr table

Revision ID: 32fa3f232c34
Revises: 13af46c70227
Create Date: 2016-04-15 09:33:52.137979

"""

# revision identifiers, used by Alembic.
revision = '32fa3f232c34'
down_revision = '13af46c70227'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('copr', sa.Column('user_id', sa.Integer(), nullable=True))

    copr_table = sa.Table(
        'copr',
        sa.MetaData(),
        sa.Column('owner_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
    )

    op.execute('UPDATE "copr" SET user_id = owner_id')

    op.drop_constraint(u'copr_owner_id_fkey', 'copr', type_='foreignkey')
    op.create_foreign_key(u'copr_user_id_fkey', 'copr', 'user', ['user_id'], ['id'])
    op.drop_column('copr', 'owner_id')


def downgrade():
    op.add_column('copr', sa.Column('owner_id', sa.INTEGER(), autoincrement=False, nullable=True))

    copr_table = sa.Table(
        'copr',
        sa.MetaData(),
        sa.Column('owner_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
    )

    op.execute('UPDATE "copr" SET owner_id = user_id')

    op.drop_constraint(u'copr_user_id_fkey', 'copr', type_='foreignkey')
    op.create_foreign_key(u'copr_owner_id_fkey', 'copr', 'user', ['owner_id'], ['id'])
    op.drop_column('copr', 'user_id')
