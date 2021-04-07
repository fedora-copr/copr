"""
Add a Copr "name" unique constraint, issue #172

Revision ID: 808912fe46d3
Revises: 6b48324e9264
Create Date: 2021-04-07 12:21:29.814687
"""

import sqlalchemy as sa
from alembic import op


revision = '808912fe46d3'
down_revision = '6b48324e9264'

def upgrade():
    text = sa.text('deleted is not true and group_id is null')
    op.create_index(
        'copr_name_for_user_uniq', 'copr', ['user_id', 'name'],
        unique=True,
        postgresql_where=text,
        sqlite_where=text,
    )

    text = sa.text('deleted is not true and group_id is not null')
    op.create_index(
        'copr_name_in_group_uniq', 'copr', ['group_id', 'name'],
        unique=True,
        postgresql_where=text,
        sqlite_where=text,
    )

def downgrade():
    op.drop_index('copr_name_in_group_uniq', table_name='copr')
    op.drop_index('copr_name_for_user_uniq', table_name='copr')
