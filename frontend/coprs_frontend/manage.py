#!/usr/bin/python3


import os
import sys
import pipes
import importlib
import click
import commands.test
import commands.create_sqlite_file
import commands.create_db
import commands.drop_db
import commands.create_chroot
import commands.alter_chroot
import commands.display_chroots
import commands.drop_chroot
import commands.branch_fedora
import commands.comment_chroot

import commands.rawhide_to_release

from flask_script import Manager
from coprs import app


commands_old = {
    # User commands
    "alter_user": "AlterUserCommand",
    "add_user": "AddUserCommand",
    "dump_user": "DumpUserCommand",

    # Whooshee indexes
    "update_indexes": "UpdateIndexesCommand",
    "update_indexes_quick": "UpdateIndexesQuickCommand",
    "update_indexes_required": "UpdateIndexesRequiredCommand",

    # Other
    "get_admins": "GetAdminsCommand",
    "fail_build": "FailBuildCommand",
    "update_graphs": "UpdateGraphsDataCommand",
    "vacuum_graphs": "RemoveGraphsDataCommand",
    "notify_outdated_chroots": "NotifyOutdatedChrootsCommand",
    "delete_outdated_chroots": "DeleteOutdatedChrootsCommand",
    "clean_expired_projects": "CleanExpiredProjectsCommand",
    "clean_old_builds": "DeleteOldBuilds",
    "delete_orphans": "DeleteOrphansCommand",
}

if os.getuid() == 0:
    sys.stderr.write("Please don't run this script as a 'root' user, use:\n")
    sys.stderr.write("$ sudo -u copr-fe {}\n".format(
            ' '.join([pipes.quote(arg) for arg in sys.argv])))
    sys.exit(1)

manager = Manager(app)
for cmdname, clsname in commands_old.items():
    module = importlib.import_module("commands.{0}".format(cmdname))
    cls = getattr(module, clsname)
    manager.add_command(cmdname, cls())

    # General commands
    app.cli.add_command(commands.test.test, "test")

    # Database commands
    app.cli.add_command(commands.create_sqlite_file.create_sqlite_file_command, "create_sqlite_file")
    app.cli.add_command(commands.create_db.create_db, "create_db")
    app.cli.add_command(commands.drop_db.drop_db, "drop_db")

    # Chroot commands
    app.cli.add_command(commands.create_chroot.create_chroot_command, "create_chroot")
    app.cli.add_command(commands.alter_chroot.alter_chroot, "alter_chroot")
    app.cli.add_command(commands.display_chroots.display_chroots, "display_chroots")
    app.cli.add_command(commands.drop_chroot.drop_chroot, "drop_chroot")
    app.cli.add_command(commands.branch_fedora.branch_fedora, "branch_fedora")
    app.cli.add_command(commands.comment_chroot.comment_chroot, "comment_chroot")

    # User commands
    #TODO

    # Whooshee indexes
    #TODO

    # Other
    #TODO
    app.cli.add_command(commands.rawhide_to_release.rawhide_to_release, "rawhide_to_release")

if __name__ == "__main__":
    # This is just temporary while migrating to flask script,
    # values in arrays are already migrated parameters.
    # Else part will be removed once migration is complete.
    if sys.argv[1] in [
        'test', 'create_sqlite_file', 'create_db', 'drop_db',
        'create_chroot', 'alter_chroot', 'display_chroots', 'drop_chroot',
        'branch_fedora', 'comment_chroot', 'rawhide_to_release']:
        app.cli()
    else:
        manager.run()
