"""
Unquote counter_stat URLs

Revision ID: 65a172e3f102
Revises: 004a017535dc
Create Date: 2022-09-14 23:28:35.890110
"""

import sqlalchemy as sa
from alembic import op
from coprs.models import CounterStat


revision = '65a172e3f102'
down_revision = '004a017535dc'


def upgrade():
    session = sa.orm.sessionmaker(bind=op.get_bind())()
    rows = (session.query(CounterStat)
            .filter(CounterStat.name.like("%\%40%"))
            .all())

    for stat in rows:
        # See PR#2274 and PR#2280
        name = stat.name.replace(":hset::%40", ":hset::@", 1)

        # We can't simply rename the stat and be done with it. There may already
        # be a row with the unquoted name.

        existing = (session.query(CounterStat)
                    .filter(CounterStat.name==name)
                    .one_or_none())

        if existing:
            existing.counter += stat.counter
            session.delete(stat)
            session.add(existing)
        else:
            stat.name = name
            session.add(stat)

    session.commit()


def downgrade():
    """
    There is no going back
    """
