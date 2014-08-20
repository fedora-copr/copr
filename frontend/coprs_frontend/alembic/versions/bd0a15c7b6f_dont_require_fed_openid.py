"""Do not require Fedora's OpenID in DB schema

Revision ID: bd0a15c7b6f
Revises: 5055336e8c44
Create Date: 2014-08-20 21:49:05.299819

"""

# revision identifiers, used by Alembic.
revision = 'bd0a15c7b6f'
down_revision = '5055336e8c44'

from alembic import op
import sqlalchemy as sa
import logging

logger = logging.getLogger('alembic')

metadata = sa.MetaData()

def username_default(oid_user):
    return oid_user.replace(".id.fedoraproject.org/", "") \
                   .replace("http://", "")

def upgrade():
    op.add_column(u'user', sa.Column('username', sa.String(length=100)))

    sa_user = sa.Table("user", metadata,
            sa.Column("id", sa.Integer),
            sa.Column("openid_name", sa.String(length=100)),
            sa.Column("username", sa.String(length=100))
    )

    for u in op.get_bind().execute(sa.select([sa_user.c.id, sa_user.c.openid_name])):
        username = username_default(u[1])
        logger.info("converting {0}'s account".format(username))
        op.get_bind().execute(sa_user.update() \
                .where(sa_user.c.id==u[0]) \
                .values(username=username))

    if op.get_bind().dialect.name != 'sqlite':
        # Pretty sad we can not set this non-nullable in SQLite
        op.alter_column("user", "username", nullable=False)
        # We can live with redundant openid_name column..
        op.drop_column(u'user', u'openid_name')


def downgrade():
    op.add_column(u'user', sa.Column(u'openid_name', sa.VARCHAR(length=100), nullable=True))

    sa_user = sa.Table("user", metadata,
            sa.Column("id", sa.Integer),
            sa.Column("openid_name", sa.String(length=100)),
            sa.Column("username", sa.String(length=100))
    )

    for u in op.get_bind().execute(sa.select([sa_user.c.id, sa_user.c.username])):
        openid_name = "http://{0}.id.fedoraproject.org/".format(str(u[1]))
        op.get_bind().execute(sa_user.update() \
                .where(sa_user.c.id==u[0]) \
                .values(openid_name=openid_name)
        )

    if op.get_bind().dialect.name != 'sqlite':
        op.drop_column(u'user', 'username')
        op.alter_column("user", "openid_name", nullable=False)
