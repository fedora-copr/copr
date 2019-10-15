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

from flask_script import Manager
from coprs import app


commands_old = {
    # Chroot commands
    "create_chroot": "CreateChrootCommand",
    "alter_chroot": "AlterChrootCommand",
    "display_chroots": "DisplayChrootsCommand",
    "drop_chroot": "DropChrootCommand",
    "branch_fedora": "BranchFedoraCommand",
    "comment_chroot": "CommentChrootCommand",

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
    "rawhide_to_release": "RawhideToReleaseCommand",
    "backend_rawhide_to_release": "BackendRawhideToReleaseCommand",
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

app.cli.add_command(commands.test.test, "test")
app.cli.add_command(commands.create_sqlite_file.create_sqlite_file_command, "create_sqlite_file")
app.cli.add_command(commands.create_db.create_db, "create_db")
app.cli.add_command(commands.drop_db.drop_db, "drop_db")

if __name__ == "__main__":
    # This is just temporary while migrating to flask script,
    # values in arrays are already migrated parameters.
    # Else part will be removed once migration is complete.
    if sys.argv[1] in ['test', 'create_sqlite_file', 'create_db', 'drop_db']:
        with app.app_context():
            app.cli()
    else:
        manager.run()
