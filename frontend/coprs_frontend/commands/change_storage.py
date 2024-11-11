"""
Change a storage for a project

Copr supports different storage solutions for repositories with the built RPM
packages (e.g. results directory on copr-backend or Pulp). This script allows to
configure the storage type for a given project and while doing so, it makes sure
DNF repositories for the project are created.

To migrate existing build results for a given project and all of its CoprDirs,
run also `copr-change-storage` script on backend.
"""

import sys
import click
from copr_common.enums import StorageEnum
from coprs import db
from coprs.logic.coprs_logic import CoprsLogic
from coprs.logic.actions_logic import ActionsLogic


@click.command()
@click.argument("fullname", required=True)
@click.argument(
    "storage",
    required=True,
    type=click.Choice(["backend", "pulp"])
)
def change_storage(fullname, storage):
    """
    Change a storage for a project
    """
    if "/" not in fullname:
        print("Must be a fullname, e.g. @copr/copr-dev")
        sys.exit(1)

    ownername, projectname = fullname.split("/", 1)
    copr = CoprsLogic.get_by_ownername_coprname(ownername, projectname)
    copr.storage = StorageEnum(storage)
    db.session.add(copr)

    action = ActionsLogic.send_createrepo(copr)
    db.session.add(action)

    db.session.commit()
    print("Configured storage for {0} to {1}".format(copr.full_name, storage))
    print("Submitted action to create repositories: {0}".format(action.id))
    print("To migrate existing build results for this project and all of its "
          "CoprDirs, run also this command on backend:")

    cmd = "sudo -u copr copr-change-storage --src backend --dst pulp "
    cmd += "--project {0}".format(fullname)
    print("    {0}".format(cmd))
