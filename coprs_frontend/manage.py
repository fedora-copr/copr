#!/usr/bin/env python

import os

import flask
from flask.ext.script import Manager, Command, Option

from coprs import app, db, models

class CreateSqliteFileCommand(Command):
    'Create the sqlite DB file (not the tables). Used for alembic, "create_db" does this automatically.'
    def run(self):
        if flask.current_app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite'):
            # strip sqlite:///
            datadir_name = os.path.dirname(flask.current_app.config['SQLALCHEMY_DATABASE_URI'][10:])
            if not os.path.exists(datadir_name):
                os.makedirs(datadir_name)

class CreateDBCommand(Command):
    'Create the DB scheme'
    def run(self, alembic_ini=None):
        CreateSqliteFileCommand().run()
        db.create_all()
            
        # load the Alembic configuration and generate the
        # version table, "stamping" it with the most recent rev:
        from alembic.config import Config
        from alembic import command
        alembic_cfg = Config(alembic_ini)
        command.stamp(alembic_cfg, "head")

    option_list = (
        Option('--alembic',
               '-f',
               dest='alembic_ini',
               help='Path to the alembic configuration file (alembic.ini)',
               required=True),
    )

class DropDBCommand(Command):
    'Delete DB'
    def run(self):
        db.drop_all()

class ChrootCommand(Command):
    option_list = (
        Option('chroot_name',
               help='Chroot name, e.g. fedora-18-x86_64.'),
    )

class CreateChrootCommand(ChrootCommand):
    'Creates a mock chroot in DB'
    def run(self, chroot_name):
        split_chroot = chroot_name.split('-')
        if len(split_chroot) < 3:
            print 'Invalid chroot format, must be "{release}-{version}-{arch}".'
        new_chroot = models.MockChroot(os_release=split_chroot[0],
                                       os_version=split_chroot[1],
                                       arch=split_chroot[2],
                                       is_active=True)
        db.session.add(new_chroot)
        db.session.commit()

class AlterChrootCommand(ChrootCommand):
    'Activates or deactivates a chroot'
    def run(self, chroot_name, action):
        split_chroot = chroot_name.split('-')
        if len(split_chroot) < 3:
            print 'Invalid chroot format, must be "{release}-{version}-{arch}".'
        chroot = models.MockChroot.query.filter(models.MockChroot.os_release==split_chroot[0],
                                                models.MockChroot.os_version==split_chroot[1],
                                                models.MockChroot.arch==split_chroot[2]).first()
        if action == 'activate':
            chroot.is_active = True
        else:
            chroot.is_active = False

        db.session.add(chroot)
        db.session.commit()

    option_list = ChrootCommand.option_list + (
            Option('--action',
                   '-a',
                   dest='action',
                   help='Action to take - currently activate or deactivate',
                   choices=['activate', 'deactivate'],
                   required=True),
    )

class DropChrootCommand(ChrootCommand):
    'Activates or deactivates a chroot'
    def run(self, chroot_name):
        split_chroot = chroot_name.split('-')
        if len(split_chroot) < 3:
            print 'Invalid chroot format, must be "{release}-{version}-{arch}".'
        chroot = models.MockChroot.query.filter(models.MockChroot.os_release==split_chroot[0],
                                                models.MockChroot.os_version==split_chroot[1],
                                                models.MockChroot.arch==split_chroot[2]).first()
        if chroot:
            db.session.delete(chroot)
            db.session.commit()

class DisplayChrootsCommand(Command):
    'Displays current mock chroots'
    def run(self, active_only):
        chroots = models.MockChroot.query
        if active_only:
            chroots = chroots.filter(models.MockChroot.is_active==True)
        for ch in chroots:
            print '{0}-{1}-{2}'.format(ch.os_release, ch.os_version, ch.arch)

    option_list = (
            Option('--active-only',
                   '-a',
                   dest='active_only',
                   help='Display only active chroots',
                   required=False,
                   action='store_true',
                   default=False),
    )

manager = Manager(app)
manager.add_command('create_sqlite_file', CreateSqliteFileCommand())
manager.add_command('create_db', CreateDBCommand())
manager.add_command('drop_db', DropDBCommand())
manager.add_command('create_chroot', CreateChrootCommand())
manager.add_command('alter_chroot', AlterChrootCommand())
manager.add_command('display_chroots', DisplayChrootsCommand())
manager.add_command('drop_chroot', DropChrootCommand())

if __name__ == '__main__':
    manager.run()
