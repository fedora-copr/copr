"""added columns to  BuildChroot

Revision ID: 57be43049e9b
Revises: 552455e5910e
Create Date: 2015-07-09 12:30:57.326992

"""

# revision identifiers, used by Alembic.
revision = '57be43049e9b'
down_revision = '552455e5910e'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(u'build_chroot', sa.Column('ended_on', sa.Integer(), nullable=True))
    op.add_column(u'build_chroot', sa.Column('started_on', sa.Integer(), nullable=True))

    bind = op.get_bind()
    connection = bind.connect()

    m_build_table = sa.Table(
        u"build",
        sa.MetaData(),
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column('ended_on', sa.Integer(), nullable=True),
        sa.Column('started_on', sa.Integer(), nullable=True),
    )
    m_build_chroot_table = sa.Table(
        u"build_chroot",
        sa.MetaData(),
        sa.Column("mock_chroot_id", sa.Integer, nullable=False),
        sa.Column("build_id", sa.Integer),
        sa.Column('ended_on', sa.Integer(), nullable=True),
        sa.Column('started_on', sa.Integer(), nullable=True)
    )

    counter = 0
    for build in connection.execute(m_build_table.select()):
        connection.execute(
            m_build_chroot_table.update()
            .where(m_build_chroot_table.c.build_id == build.id)
            .values(
                started_on=build.started_on,
                ended_on=build.ended_on,
            )
        )
        counter += 1
        if counter % 1000 == 0:
            print("Processed: {} builds".format(counter))


def downgrade():
    op.drop_column(u'build_chroot', 'started_on')
    op.drop_column(u'build_chroot', 'ended_on')
