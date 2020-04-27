"""
Add BuildChroot.id and CoprChroot.id

Revision ID: 4d06318043d3
Revises: 6f83ea2ba416
Create Date: 2020-04-22 13:37:56.137818
"""

import time

import sqlalchemy as sa
from alembic import op

revision = '4d06318043d3'
down_revision = '6f83ea2ba416'

Base = sa.ext.declarative.declarative_base()

FIRST_TIME = time.time()


def _info_checkpoint(message):
    secs = time.time() - FIRST_TIME
    print("{:6.2f} {}".format(secs, message))


def upgrade():
    _info_checkpoint("add CoprChroot.id (and index)")
    op.execute("ALTER TABLE copr_chroot ADD COLUMN id SERIAL")
    op.create_index('temporary_copr_chroot_id', 'copr_chroot', ['id'],
                    unique=True)

    _info_checkpoint("add BuildChroot.copr_chroot_id column")
    op.add_column('build_chroot',
                  sa.Column('copr_chroot_id', sa.Integer(), nullable=True))

    _info_checkpoint("creating temporary table with index")
    op.execute("""
    CREATE TEMP TABLE temporary_table AS (
        SELECT
            bch.build_id as build_id,
            bch.mock_chroot_id,
            c.id as copr_id,
            cch.id as copr_chroot_id
        FROM
            build_chroot as bch
        LEFT JOIN
            build as b on bch.build_id = b.id
        LEFT JOIN
            copr as c on c.id = b.copr_id
        LEFT JOIN
            copr_chroot as cch ON cch.copr_id = c.id AND
                                  cch.mock_chroot_id = bch.mock_chroot_id
    )
    """)
    op.execute("""
    CREATE INDEX temporary_index ON temporary_table (build_id, mock_chroot_id)
    """)

    _info_checkpoint("drop constraints/indexes to speedup update")
    op.drop_constraint('build_chroot_pkey', 'build_chroot', type_='primary')
    # drop those temporarily
    op.drop_index('ix_build_chroot_build_id', table_name='build_chroot')
    op.drop_index('ix_build_chroot_started_on', table_name='build_chroot')
    op.drop_index('ix_build_chroot_ended_on', table_name='build_chroot')
    op.drop_index('build_chroot_status_started_on_idx',
                  table_name='build_chroot')

    _info_checkpoint("add BuildChroot.id")
    op.execute("ALTER TABLE build_chroot ADD COLUMN id SERIAL")

    _info_checkpoint("starting the expensive query")
    sql_major_query = """
    UPDATE
        build_chroot
    SET
        copr_chroot_id = sq.copr_chroot_id
    FROM
        temporary_table as sq
    WHERE
        build_chroot.mock_chroot_id = sq.mock_chroot_id AND
        build_chroot.build_id = sq.build_id
    """
    op.execute(sql_major_query)

    _info_checkpoint("creating other constraints")
    op.create_unique_constraint('copr_chroot_mock_chroot_id_copr_id_uniq',
                                'copr_chroot', ['mock_chroot_id', 'copr_id'])

    _info_checkpoint("drop the temporary stuff")
    op.drop_table('temporary_table')

    # those were temporarily removed
    _info_checkpoint("create temporarily removed constraints/indexes")
    op.create_index('build_chroot_status_started_on_idx', 'build_chroot',
                    ['status', 'started_on'], unique=False)
    op.create_index(op.f('ix_build_chroot_build_id'), 'build_chroot',
                    ['build_id'], unique=False)
    op.create_index(op.f('ix_build_chroot_started_on'), 'build_chroot',
                    ['started_on'], unique=False)
    op.create_index(op.f('ix_build_chroot_ended_on'), 'build_chroot',
                    ['ended_on'], unique=False)

    _info_checkpoint("create changed indexes/constraints")
    op.create_primary_key('build_chroot_pkey', 'build_chroot', ['id'])
    op.create_unique_constraint('build_chroot_mock_chroot_id_build_id_uniq',
                                'build_chroot', ['mock_chroot_id', 'build_id'])
    op.create_index(op.f('ix_build_chroot_copr_chroot_id'), 'build_chroot',
                    ['copr_chroot_id'], unique=False)

    op.drop_constraint('copr_chroot_pkey', 'copr_chroot', type_='primary')
    op.create_primary_key('copr_chroot_pkey', 'copr_chroot', ['id'])
    op.drop_index('temporary_copr_chroot_id', table_name='copr_chroot')
    op.create_foreign_key(None, 'build_chroot', 'copr_chroot',
                          ['copr_chroot_id'], ['id'], ondelete='SET NULL')


def downgrade():
    """ not implemented """
    raise NotImplementedError("Sorry, this migration cannot be undone")
