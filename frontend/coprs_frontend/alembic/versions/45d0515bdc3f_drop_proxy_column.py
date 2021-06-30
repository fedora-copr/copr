"""
drop proxy column

Revision ID: 45d0515bdc3f
Revises: e2b1cb42e6b7
Create Date: 2021-06-22 13:10:48.699369
"""

import sqlalchemy as sa
from alembic import op


revision = '45d0515bdc3f'
down_revision = 'e2b1cb42e6b7'


def upgrade():
    op.execute("""delete from user_private  where user_id=(select id from "user" WHERE proxy = true);""")
    op.execute("""delete from "user" where proxy = true;""")
    op.drop_column('user', 'proxy')


def downgrade():
    op.add_column('user', sa.Column('proxy', sa.BOOLEAN(), autoincrement=False, nullable=True))
