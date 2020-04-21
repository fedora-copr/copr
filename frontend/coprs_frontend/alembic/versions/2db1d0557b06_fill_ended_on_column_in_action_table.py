"""
fill ended_on column in Action table

Revision ID: 2db1d0557b06
Revises: 4ed794df3bbb
Create Date: 2019-12-10 08:40:15.126168
"""

import sqlalchemy as sa
from alembic import op


revision = '2db1d0557b06'
down_revision = '4ed794df3bbb'

def upgrade():
    op.execute(
        'UPDATE action SET ended_on = created_on + 5\
         WHERE (result = 1 or result = 2) AND ended_on IS NULL'
    )

def downgrade():
    pass
