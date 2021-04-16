"""
fixup source_status

Revision ID: d8a1062ee4cf
Revises: 808912fe46d3
Create Date: 2021-04-16 16:03:58.538926
"""

import sqlalchemy as sa
from alembic import op


revision = 'd8a1062ee4cf'
down_revision = '808912fe46d3'

def upgrade():
    session = sa.orm.sessionmaker(bind=op.get_bind())()

    # Prior the commit b9326e8d997bcbbd818018cac84398e83322d3c6, we didn't have
    # source_status at all.  Since then we never put NULL value in the
    # source_status field.  Even though all the old NULL values there are old,
    # they caused quite some problems with the state/status logic, so let's
    # avoid the NULL value there now.
    session.execute("""
        UPDATE build SET source_status = 1 WHERE source_status is NULL;
        UPDATE build SET source_status = 0 WHERE id IN (
            SELECT build.id FROM build
            LEFT OUTER JOIN build_chroot
            ON build.id = build_chroot.build_id
            WHERE build_chroot.id IS null AND source_status = 1);
    """)
    op.alter_column('build', 'source_status',
                    existing_type=sa.INTEGER(),
                    nullable=False)

def downgrade():
    op.alter_column('build', 'source_status',
                    existing_type=sa.INTEGER(),
                    nullable=True)
