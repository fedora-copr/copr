#!/usr/bin/python3


import importlib
from flask_script import Manager
from coprs import app


commands = {
    # General commands
    "test": "TestCommand",

    # Database commands
    "create_sqlite_file": "CreateSqliteFileCommand",
    "create_db": "CreateDBCommand",
    "drop_db": "DropDBCommand",

    # Chroot commands
    "create_chroot": "CreateChrootCommand",
    "alter_chroot": "AlterChrootCommand",
    "display_chroots": "DisplayChrootsCommand",
    "drop_chroot": "DropChrootCommand",

    # User commands
    "alter_user": "AlterUserCommand",
    "add_user": "AddUserCommand",
    "dump_user": "DumpUserCommand",

    # Other
    "get_admins": "GetAdminsCommand",
    "fail_build": "FailBuildCommand",
    "update_indexes": "UpdateIndexesCommand",
    "update_indexes_quick": "UpdateIndexesQuickCommand",
    "rawhide_to_release": "RawhideToReleaseCommand",
    "backend_rawhide_to_release": "BackendRawhideToReleaseCommand",
    "update_graphs": "UpdateGraphsDataCommand",
    "vacuum_graphs": "RemoveGraphsDataCommand",
    "notify_outdated_chroots": "NotifyOutdatedChrootsCommand",
}


manager = Manager(app)
for cmdname, clsname in commands.items():
    module = importlib.import_module("commands.{0}".format(cmdname))
    cls = getattr(module, clsname)
    manager.add_command(cmdname, cls())


if __name__ == "__main__":
    manager.run()
