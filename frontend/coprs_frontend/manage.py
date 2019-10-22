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
import commands.alter_user
import commands.add_user
import commands.dump_user
import commands.update_indexes
import commands.update_indexes_quick
import commands.update_indexes_required
import commands.get_admins
import commands.fail_build
import commands.rawhide_to_release
import commands.update_graphs
import commands.vacuum_graphs
import commands.notify_outdated_chroots
import commands.delete_outdated_chroots
import commands.clean_expired_projects
import commands.clean_old_builds
import commands.delete_orphans

from flask_script import Manager
from coprs import app

if os.getuid() == 0:
    sys.stderr.write("Please don't run this script as a 'root' user, use:\n")
    sys.stderr.write("$ sudo -u copr-fe {}\n".format(
            ' '.join([pipes.quote(arg) for arg in sys.argv])))
    sys.exit(1)

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
app.cli.add_command(commands.alter_user.alter_user, "alter_user")
app.cli.add_command(commands.add_user.add_user, "add_user")
app.cli.add_command(commands.dump_user.dump_user, "dump_user")

# Whooshee indexes
app.cli.add_command(commands.update_indexes.update_indexes, "update_indexes")
app.cli.add_command(commands.update_indexes_quick.update_indexes_quick, "update_indexes_quick")
app.cli.add_command(commands.update_indexes_required.update_indexes_required, "update_indexes_required")

# Other
app.cli.add_command(commands.get_admins.get_admins, "get_admins")
app.cli.add_command(commands.fail_build.fail_build, "fail_build")
app.cli.add_command(commands.rawhide_to_release.rawhide_to_release, "rawhide_to_release")
app.cli.add_command(commands.update_graphs.update_graphs, "update_graphs")
app.cli.add_command(commands.vacuum_graphs.vacuum_graphs, "vacuum_graphs")
app.cli.add_command(commands.notify_outdated_chroots.notify_outdated_chroots, "notify_outdated_chroots")
app.cli.add_command(commands.delete_outdated_chroots.delete_outdated_chroots, "delete_outdated_chroots")
app.cli.add_command(commands.clean_expired_projects.clean_expired_projects, "clean_expired_projects")
app.cli.add_command(commands.clean_old_builds.clean_old_builds, "clean_old_builds")
app.cli.add_command(commands.delete_orphans.delete_orphans, "delete_orphans")

if __name__ == "__main__":
    app.cli()
