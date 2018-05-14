"""generate main copr_dirs

Revision ID: 3637b9daf7e4
Revises: 887cbbd6575e
Create Date: 2018-06-25 23:18:56.969792

"""

# revision identifiers, used by Alembic.
revision = '3637b9daf7e4'
down_revision = '887cbbd6575e'

from alembic import op
import sqlalchemy as sa


def upgrade():
    session = sa.orm.sessionmaker(bind=op.get_bind())()
    session.execute("""INSERT INTO copr_dir (name,copr_id,main) (SELECT name,id,True FROM copr) ON CONFLICT DO NOTHING;""")
    session.execute("""UPDATE package SET copr_dir_id=(SELECT id from copr_dir where copr_dir.copr_id=package.copr_id AND copr_dir.main = True) WHERE copr_dir_id = NULL""")
    session.execute("""UPDATE build SET copr_dir_id=(SELECT id from copr_dir where copr_dir.copr_id=build.copr_id AND copr_dir.main = True) WHERE copr_dir_id = NULL""")


def downgrade():
    pass
