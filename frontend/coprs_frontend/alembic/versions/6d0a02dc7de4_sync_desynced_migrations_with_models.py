"""
Sync desynced migrations with models

Revision ID: 6d0a02dc7de4
Revises: d2fbc2ab630d
Create Date: 2020-04-21 14:40:31.230986
"""

from alembic import op


revision = '6d0a02dc7de4'
down_revision = 'd2fbc2ab630d'


def _index_missing(bind, index_name):
    return not (
        bind.execute("SELECT count(*) FROM pg_indexes "
                     "WHERE indexname = '{}'".format(index_name))
        .first()[0]
    )


def upgrade():
    bind = op.get_bind()

    # sorry, PostgreSQL only
    assert bind.dialect.name == 'postgresql'

    # We need the `ix_` naming, otherwise `alembic revision --autogenerate`
    # doesn't match the existing index with our model.
    bind.execute("ALTER INDEX IF EXISTS build_copr_id RENAME TO ix_build_copr_id")
    bind.execute("ALTER INDEX IF EXISTS build_package_idx RENAME TO ix_build_package_id")
    bind.execute("ALTER INDEX IF EXISTS build_user_id_idx RENAME TO ix_build_user_id")
    bind.execute("ALTER INDEX IF EXISTS build_chroot_build_id RENAME TO ix_build_chroot_build_id")
    bind.execute("ALTER INDEX IF EXISTS copr_user_id_idx RENAME TO ix_copr_user_id")
    bind.execute("ALTER INDEX IF EXISTS copr_chroot_copr_id RENAME TO ix_copr_chroot_copr_id")
    bind.execute("ALTER INDEX IF EXISTS copr_permission_copr_id RENAME TO ix_copr_permission_copr_id")
    bind.execute("ALTER INDEX IF EXISTS legal_flag_resolved_on RENAME TO ix_legal_flag_resolved_on")
    bind.execute("ALTER INDEX IF EXISTS package_copr_id_idx  RENAME TO ix_package_copr_id")

    # Those are pretty good to have.
    op.create_foreign_key(None, 'build', 'package', ['package_id'], ['id'])
    op.create_foreign_key(None, 'copr', 'group', ['group_id'], ['id'])

    # Fixing issue #1346, this is redundant.
    if not _index_missing(bind, 'unique_name_stream_version_copr_id'):
        op.drop_constraint('unique_name_stream_version_copr_id', 'module',
                           type_='unique')

    # We lived without this because FAS/Kerberos provides unique usernames, but
    # it's better to have it.
    op.create_unique_constraint(None, 'user', ['username'])

    # For some reaons some of those were missing in some of our Copr instances.
    if _index_missing(bind, 'action_result_action_type'):
        op.create_index('action_result_action_type', 'action', ['result', 'action_type'], unique=False)
    if _index_missing(bind, 'ix_build_chroot_build_id'):
        op.create_index(op.f('ix_build_chroot_build_id'), 'build_chroot', ['build_id'], unique=False)
    if _index_missing(bind, 'copr_deleted_name'):
        op.create_index('copr_deleted_name', 'copr', ['deleted', 'name'], unique=False)
    if _index_missing(bind, 'ix_copr_chroot_copr_id'):
        op.create_index(op.f('ix_copr_chroot_copr_id'), 'copr_chroot', ['copr_id'], unique=False)
    if _index_missing(bind, 'ix_copr_permission_copr_id'):
        op.create_index(op.f('ix_copr_permission_copr_id'), 'copr_permission', ['copr_id'], unique=False)
    if _index_missing(bind, 'ix_legal_flag_resolved_on'):
        op.create_index(op.f('ix_legal_flag_resolved_on'), 'legal_flag', ['resolved_on'], unique=False)

def downgrade():
    """ no way back, sorry """
