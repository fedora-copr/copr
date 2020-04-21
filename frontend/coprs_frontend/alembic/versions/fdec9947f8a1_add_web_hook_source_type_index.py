"""add web_hook,source_type index

Revision ID: fdec9947f8a1
Revises: 669ba46bf357
Create Date: 2017-10-11 13:45:59.512011

"""

# revision identifiers, used by Alembic.
revision = 'fdec9947f8a1'
down_revision = '669ba46bf357'

from alembic import op


def upgrade():
    op.create_index('package_webhook_sourcetype', 'package', ['webhook_rebuild', 'source_type'])
    op.create_index('copr_webhook_secret', 'copr', ['webhook_secret'])

def downgrade():
    op.drop_index('package_webhook_sourcetype')
    op.drop_index('copr_webhook_secret')
