"""copy private data to private tables

Revision ID: 7723d580c625
Revises: 29c352bde564
Create Date: 2018-12-03 13:49:15.501999

"""

# revision identifiers, used by Alembic.
revision = '7723d580c625'
down_revision = '29c352bde564'

from alembic import op
import sqlalchemy as sa


def upgrade():
    session = sa.orm.sessionmaker(bind=op.get_bind())()
    session.execute("""INSERT INTO copr_private(webhook_secret, scm_api_auth_json, copr_id)
                    (select webhook_secret, scm_api_auth_json, id from copr);""")
    session.execute("""INSERT INTO user_private(mail, timezone, api_login, api_token, api_token_expiration, user_id)
                    (select mail, timezone, api_login, api_token, api_token_expiration, id as user_id from \"user\");""")

def downgrade():
    # no downgrade
    pass
