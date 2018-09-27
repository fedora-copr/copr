"""Unique constraint on modules

Revision ID: f61a5c930abf
Revises: 3b0851cb25fc
Create Date: 2017-12-27 16:32:51.786669

"""

# revision identifiers, used by Alembic.
revision = 'f61a5c930abf'
down_revision = '3b0851cb25fc'

from alembic import op


def upgrade():
    op.create_unique_constraint('copr_name_stream_version_uniq', 'module', ['copr_id', 'name', 'stream', 'version'])


def downgrade():
    op.drop_constraint('copr_name_stream_version_uniq', 'module', type_='unique')
