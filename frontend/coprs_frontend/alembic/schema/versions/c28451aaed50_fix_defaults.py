"""fix_defaults

Revision ID: c28451aaed50
Revises: 3637b9daf7e4
Create Date: 2018-09-06 11:01:33.936413

"""

# revision identifiers, used by Alembic.
revision = 'c28451aaed50'
down_revision = '3637b9daf7e4'

from alembic import op


def upgrade():
    op.alter_column('copr', 'follow_fedora_branching', server_default='t')
    op.alter_column('copr', 'use_bootstrap_container', server_default='f')


def downgrade():
    op.alter_column('copr', 'follow_fedora_branching', server_default='f')
    op.alter_column('copr', 'use_bootstrap_container', server_default='t')
