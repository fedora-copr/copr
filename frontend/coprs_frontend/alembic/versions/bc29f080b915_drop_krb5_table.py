"""
drop krb5 table

Revision ID: bc29f080b915
Revises: 65a172e3f102
Create Date: 2022-11-16 16:28:25.759413
"""

import sqlalchemy as sa
from alembic import op


revision = 'bc29f080b915'
down_revision = '65a172e3f102'

def upgrade():
    op.drop_table('krb5_login')

def downgrade():
    op.create_table('krb5_login',
    sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('primary', sa.VARCHAR(length=80), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='krb5_login_user_id_fkey')
    )
