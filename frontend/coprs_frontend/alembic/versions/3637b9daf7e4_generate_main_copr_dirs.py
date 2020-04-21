"""generate main copr_dirs

Revision ID: 3637b9daf7e4
Revises: ac5917e5c4fe
Create Date: 2018-06-25 23:18:56.969792

"""

# revision identifiers, used by Alembic.
revision = '3637b9daf7e4'
down_revision = 'ac5917e5c4fe'

from alembic import op
import sqlalchemy as sa


def upgrade():
    session = sa.orm.sessionmaker(bind=op.get_bind())()

    session.execute("""INSERT INTO copr_dir (name,copr_id,ownername,main)
                    (SELECT copr.name,copr.id,concat('@', "group".name),True FROM copr JOIN "group" ON copr.group_id = "group".id WHERE copr.deleted=False)
                    ON CONFLICT DO NOTHING;""")

    session.execute("""
                    INSERT INTO copr_dir (name,copr_id,ownername,main)
                    (SELECT copr.name,copr.id,username,True FROM copr JOIN "user" ON copr.user_id = "user".id WHERE copr.deleted=False AND copr.group_id is NULL)
                    ON CONFLICT DO NOTHING;""")

    session.execute("""UPDATE package SET copr_dir_id=(SELECT id from copr_dir where copr_dir.copr_id=package.copr_id AND copr_dir.main=True) WHERE copr_dir_id is NULL""")
    session.execute("""UPDATE build SET copr_dir_id=(SELECT id from copr_dir where copr_dir.copr_id=build.copr_id AND copr_dir.main=True) WHERE copr_dir_id is NULL""")


def downgrade():
    pass
