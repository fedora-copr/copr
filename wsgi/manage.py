#!/usr/bin/env python

import argparse
import os

from coprs import app, db

class DBManager(object):
    def __init__(self, db):
        self.db = db

    def create_sqlite_file(self):
        if app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite'):
            # strip sqlite:///
            datadir_name = os.path.dirname(app.config['SQLALCHEMY_DATABASE_URI'][10:])
            if not os.path.exists(datadir_name):
                os.makedirs(datadir_name)

    def create_db(self):
        self.create_sqlite_file()
        self.db.create_all()

    def delete_db(self):
        self.db.drop_all()

parser = argparse.ArgumentParser(description = 'Manage the app')
parser.add_argument('-s', '--create-sqlite-file',
                    required = False,
                    help = 'Create the sqlite DB file (not the tables). User for alembic, the -c does this automatically.',
                    action = 'store_true')

parser.add_argument('-c', '--create-db',
                    required = False,
                    help = 'Create the DB scheme',
                    action = 'store_true')

parser.add_argument('-d', '--delete-db',
                    required = False,
                    help = 'Delete DB',
                    action = 'store_true')

args = parser.parse_args()

manager = DBManager(db)
if args.create_sqlite_file:
    manager.create_sqlite_file()
elif args.create_db:
    manager.create_db()
elif args.delete_db:
    manager.delete_db()
