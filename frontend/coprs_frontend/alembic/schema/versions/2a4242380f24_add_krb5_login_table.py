"""Add 'krb5_login' table

Revision ID: 2a4242380f24
Revises: bd0a15c7b6f
Create Date: 2014-08-21 11:40:19.181293

"""

# revision identifiers, used by Alembic.
revision = '2a4242380f24'
down_revision = 'bd0a15c7b6f'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('krb5_login',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('config_name', sa.String(length=30), nullable=False),
        sa.Column('primary', sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('primary', 'config_name')
    )

def downgrade():
    op.drop_table('krb5_login')
