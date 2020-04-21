"""
Drop alembic_fedora_version table.

Revision ID: d2fbc2ab630d
Revises: 58eab04e5afc
Create Date: 2020-04-21 14:28:14.518134
"""

from alembic import op


revision = 'd2fbc2ab630d'
down_revision = '58eab04e5afc'


def upgrade():
    engine = op.get_bind()
    if engine.dialect.has_table(engine, 'alembic_fedora_version'):
        op.drop_table('alembic_fedora_version')


def downgrade():
    """ not implemented, sorry """
