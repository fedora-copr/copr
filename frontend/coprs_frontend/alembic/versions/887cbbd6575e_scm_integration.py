"""scm integration

Revision ID: 887cbbd6575e
Revises: acac8d3ae868
Create Date: 2018-07-16 11:32:26.554253

"""

# revision identifiers, used by Alembic.
revision = '887cbbd6575e'
down_revision = 'acac8d3ae868'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # new copr_dir table
    op.create_table('copr_dir',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.Text(), nullable=True),
    sa.Column('main', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('copr_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['copr_id'], ['copr.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('copr_id', 'name', name='copr_dir_copr_id_name_uniq')
    )
    op.create_index(op.f('ix_copr_dir_copr_id'), 'copr_dir', ['copr_id'], unique=False)
    op.create_index(op.f('ix_copr_dir_name'), 'copr_dir', ['name'], unique=False)
    op.create_index('only_one_main_copr_dir', 'copr_dir', ['copr_id', 'main'], unique=True, postgresql_where=sa.text(u'main = true'))

    # scm integration properties for Build + copr_dir relation
    op.add_column(u'build', sa.Column('copr_dir_id', sa.Integer(), nullable=True))
    op.add_column(u'build', sa.Column('scm_object_id', sa.Text(), nullable=True))
    op.add_column(u'build', sa.Column('scm_object_type', sa.Text(), nullable=True))
    op.add_column(u'build', sa.Column('scm_object_url', sa.Text(), nullable=True))
    op.add_column(u'build', sa.Column('update_callback', sa.Text(), nullable=True))
    op.create_index(op.f('ix_build_copr_dir_id'), 'build', ['copr_dir_id'], unique=False)
    op.create_foreign_key('build_copr_dir_id_fkey', 'build', 'copr_dir', ['copr_dir_id'], ['id'])

    # scm integration properties for Copr
    op.add_column(u'copr', sa.Column('scm_api_auth_json', sa.Text(), nullable=True))
    op.add_column(u'copr', sa.Column('scm_api_type', sa.Text(), nullable=True))
    op.add_column(u'copr', sa.Column('scm_repo_url', sa.Text(), nullable=True))

    # package constraint changes + copr_dir relation
    op.add_column(u'package', sa.Column('copr_dir_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_package_copr_dir_id'), 'package', ['copr_dir_id'], unique=False)
    op.create_unique_constraint('packages_copr_dir_pkgname', 'package', ['copr_dir_id', 'name'])
    op.drop_constraint(u'packages_copr_pkgname', 'package', type_='unique')
    op.create_foreign_key('package_copr_dir_id_fkey', 'package', 'copr_dir', ['copr_dir_id'], ['id'])


def downgrade():
    op.drop_constraint('package_copr_dir_id_fkey', 'package', type_='foreignkey')
    op.create_unique_constraint(u'packages_copr_pkgname', 'package', ['copr_id', 'name'])
    op.drop_constraint('packages_copr_dir_pkgname', 'package', type_='unique')
    op.drop_index(op.f('ix_package_copr_dir_id'), table_name='package')
    op.drop_column(u'package', 'copr_dir_id')
    op.drop_column(u'copr', 'scm_repo_url')
    op.drop_column(u'copr', 'scm_api_type')
    op.drop_column(u'copr', 'scm_api_auth_json')
    op.drop_constraint('build_copr_dir_id_fkey', 'build', type_='foreignkey')
    op.drop_index(op.f('ix_build_copr_dir_id'), table_name='build')
    op.drop_column(u'build', 'update_callback')
    op.drop_column(u'build', 'scm_object_url')
    op.drop_column(u'build', 'scm_object_type')
    op.drop_column(u'build', 'scm_object_id')
    op.drop_column(u'build', 'copr_dir_id')
    op.drop_index('only_one_main_copr_dir', table_name='copr_dir')
    op.drop_index(op.f('ix_copr_dir_name'), table_name='copr_dir')
    op.drop_index(op.f('ix_copr_dir_copr_id'), table_name='copr_dir')
    op.drop_table('copr_dir')
