"""
drop config_name column from krb5_login

Revision ID: 5ecebe072cb7
Revises: 9409fc1d5895
Create Date: 2022-03-14 10:17:19.185416
"""

import sqlalchemy as sa
from alembic import op


revision = '5ecebe072cb7'
down_revision = '9409fc1d5895'


def upgrade():
    op.drop_column('krb5_login', 'config_name')


def downgrade():
    op.add_column('krb5_login', sa.Column('config_name', sa.VARCHAR(length=30), autoincrement=False, nullable=False))
