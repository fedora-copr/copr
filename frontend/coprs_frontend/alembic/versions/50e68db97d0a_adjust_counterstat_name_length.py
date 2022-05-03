"""
Adjust CounterStat.name length

Revision ID: 50e68db97d0a
Revises: 5ecebe072cb7
Create Date: 2022-05-03 17:20:31.789922
"""

import sqlalchemy as sa
from alembic import op


revision = '50e68db97d0a'
down_revision = '5ecebe072cb7'


def upgrade():
    op.alter_column("counter_stat", "name", type_=sa.Text)

def downgrade():
    op.alter_column("counter_stat", "name", type_=sa.String(127))
