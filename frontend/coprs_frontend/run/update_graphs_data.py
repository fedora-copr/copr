#!/usr/bin/env python3

import argparse
import sys
import os
from time import time

from sqlalchemy import and_, or_

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
)

from coprs import db, models
from coprs.logic.builds_logic import BuildsLogic

parser = argparse.ArgumentParser(description='Update cached data for graphs of usage.')
parser.add_argument('--update', action='store_true', help='Process data not yet cached.')
parser.add_argument('--remove', action='store_true', help='Remove old data.')

db.engine.connect()


def update_data():
    curr_time = int(time())
    BuildsLogic.get_tasks_histogram('10min', curr_time - 86599, curr_time, 600)
    BuildsLogic.get_tasks_histogram('24h', curr_time - 90*86400, curr_time, 86400)


def remove_old_data():
    curr_time = int(time())

    models.BuildsStatistics.query.filter(or_(
        and_(models.BuildsStatistics.time < curr_time - 91 * 86400,
             models.BuildsStatistics.stat_type == '24h'),
        and_(models.BuildsStatistics.time < curr_time - 87000,
             models.BuildsStatistics.stat_type == '10min')
    )).delete()
    db.session.commit()


def main():
    args = parser.parse_args()
    if args.update:
        update_data()
    if args.remove:
        remove_old_data()


if __name__ == '__main__':
    main()
