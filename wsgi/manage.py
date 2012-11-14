#!/usr/bin/env python

import argparse

from coprs import db

class DBManager(object):
    def __init__(self, db):
        self.db = db

    def create_db(self):
        self.db.create_all()

    def delete_db(self):
        self.db.drop_all()

parser = argparse.ArgumentParser(description = 'Manage the app')
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
if args.create_db:
    manager.create_db()
elif args.delete_db:
    manager.delete_db()
