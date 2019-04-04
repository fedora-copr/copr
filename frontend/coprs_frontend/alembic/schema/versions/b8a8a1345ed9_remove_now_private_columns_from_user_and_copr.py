"""Remove now private columns from user and copr

Revision ID: b8a8a1345ed9
Revises: 7723d580c625
Create Date: 2019-01-09 13:03:12.138976

"""

# revision identifiers, used by Alembic.
revision = 'b8a8a1345ed9'
down_revision = '7723d580c625'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_column('copr', 'webhook_secret')
    op.drop_column('copr', 'scm_api_auth_json')
    op.drop_column('user', 'api_login')
    op.drop_column('user', 'timezone')
    op.drop_column('user', 'mail')
    op.drop_column('user', 'api_token_expiration')
    op.drop_column('user', 'api_token')

def downgrade():
    raise Exception("revision '{}' contains an irreversible migration".format(revision))
