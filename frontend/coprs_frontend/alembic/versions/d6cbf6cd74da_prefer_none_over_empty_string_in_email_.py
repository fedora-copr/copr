"""
prefer None over empty string in email and homepage

Revision ID: d6cbf6cd74da
Revises: b14b27e4a795
Create Date: 2020-11-24 09:53:05.334633
"""

import sqlalchemy as sa
from alembic import op


revision = 'd6cbf6cd74da'
down_revision = 'b14b27e4a795'

def upgrade():
    session = sa.orm.sessionmaker(bind=op.get_bind())()
    session.execute("UPDATE copr SET homepage = null WHERE homepage = ''")
    session.execute("UPDATE copr SET contact = null  WHERE contact = ''")

def downgrade():
    """
    No way back is needed, even before this migration we had NULL values in
    many rows and it did not break anything
    """
