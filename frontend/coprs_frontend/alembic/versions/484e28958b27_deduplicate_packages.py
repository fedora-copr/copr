"""
deduplicate packages, issue 617

Revision ID: 484e28958b27
Revises: 50e68db97d0a
Create Date: 2022-05-25 10:54:34.832625
"""

import logging

import sqlalchemy as sa
from alembic import op

revision = '484e28958b27'
down_revision = '50e68db97d0a'

log = logging.getLogger(__name__)

def upgrade():
    """
    Before we drop the Package.copr_dir_id argument, use it to "guess" the
    "main" package within each Copr.  That is to be kept, rest of the Package
    of the same name are to be removed.
    """
    session = sa.orm.sessionmaker(bind=op.get_bind())()

    # About 9k items here, 28k packages for de-duplication.
    duplications = session.execute(
        """
        select count(package.name), package.name, copr.id
        from package
        join copr on copr.id = package.copr_id
        group by copr.id, package.name
        having count(package.name) > 1;
        """
    )

    for duplication in duplications:
        _, package_name, copr_id = duplication

        fix_package_ids_result = session.execute(
            """
            select package.id
            from package
            left join copr_dir on package.copr_dir_id = copr_dir.id
            where package.copr_id = :copr_id and package.name = :package_name
            order by copr_dir.main = false asc, package.id asc;
            """,
            {"copr_id": copr_id, "package_name": package_name},
        )

        fix_ids = []
        main_package_id = None
        for row in fix_package_ids_result:
            package_id = row[0]
            if main_package_id is None:
                main_package_id = package_id
            else:
                fix_ids.append(package_id)

        log.debug(
            "Deduplicating %s=%s in copr_id=%s, affected packages: %s",
            package_name, main_package_id, copr_id,
            ", ".join([str(x) for x in fix_ids]),
        )

        session.execute(
            """
            update build set package_id = :package_id
            where package_id in :ids;
            """,
            {"package_id": main_package_id, "ids": tuple(fix_ids)},
        )

        session.execute(
            "delete from package where id in :ids",
            {"ids": tuple(fix_ids)},
        )

    log.debug("Removing indexes and constraints")
    op.drop_index('ix_package_copr_dir_id', table_name='package')
    op.drop_constraint('packages_copr_dir_pkgname', 'package', type_='unique')
    op.drop_constraint('package_copr_dir_foreign_key', 'package', type_='foreignkey')
    op.drop_column('package', 'copr_dir_id')
    # make this unique
    op.drop_index('package_copr_id_name', table_name='package')
    op.create_index('package_copr_id_name', 'package', ['copr_id', 'name'], unique=True)


def downgrade():
    op.add_column('package', sa.Column('copr_dir_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.create_foreign_key('package_copr_dir_foreign_key', 'package', 'copr_dir', ['copr_dir_id'], ['id'])
    op.create_unique_constraint('packages_copr_dir_pkgname', 'package', ['copr_dir_id', 'name'])
    op.create_index('ix_package_copr_dir_id', 'package', ['copr_dir_id'], unique=False)
    op.drop_index('package_copr_id_name', table_name='package')
    op.create_index('package_copr_id_name', 'package', ['copr_id', 'name'], unique=False)
