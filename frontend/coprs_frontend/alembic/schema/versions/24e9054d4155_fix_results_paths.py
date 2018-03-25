"""fix results paths

Revision ID: 24e9054d4155
Revises: 465202bfb9ce
Create Date: 2018-03-23 23:42:26.434785

"""

# revision identifiers, used by Alembic.
revision = '24e9054d4155'
down_revision = '465202bfb9ce'

from alembic import op
import sqlalchemy as sa


def upgrade():
    session = sa.orm.sessionmaker(bind=op.get_bind())()

    op.add_column('build', sa.Column('result_dir', sa.Text(), nullable=False, server_default=''))
    op.add_column('build_chroot', sa.Column('result_dir', sa.Text(), nullable=True, server_default=''))

    # Note that there are old builddirs on backend that do not conform to 00123456-package_name naming
    # they come from era before dist-git, hence SELECT CASE WHEN build_chroot.git_hash is not NULL AND build_chroot.git_hash != ''
    session.execute("""
        UPDATE build_chroot AS updated_build_chroot SET
            result_dir=(SELECT CASE WHEN build_chroot.git_hash is not NULL AND build_chroot.git_hash != ''
                    THEN concat(lpad(CAST(build.id AS text), 8, '0'), '-', package.name)
                    ELSE regexp_replace((regexp_split_to_array(build.pkgs, '/'))[array_length(regexp_split_to_array(build.pkgs, '/'), 1)], '.src.rpm$', '') END
                    FROM build_chroot JOIN build ON build.id = build_chroot.build_id JOIN package ON build.package_id = package.id
                    WHERE updated_build_chroot.build_id = build_chroot.build_id AND updated_build_chroot.mock_chroot_id = build_chroot.mock_chroot_id AND
                        build.results is not NULL AND build.results != '');
    """)
    session.execute("UPDATE build_chroot SET result_dir = '' WHERE result_dir IS NULL;")
    session.execute("ALTER TABLE build_chroot ALTER COLUMN result_dir SET NOT NULL;")
    session.execute("UPDATE build SET result_dir=lpad(CAST(build.id AS text), 8, '0') WHERE build.results is not NULL and build.results != '';")

def downgrade():
    op.drop_column('build', 'result_dir')
    op.drop_column('build_chroot', 'result_dir')
