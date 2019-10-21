import click

from flask_script import Command, Option
from coprs import exceptions
from coprs import db
from coprs.helpers import chroot_to_branch
from coprs.logic import coprs_logic


def print_invalid_format(chroot_name):
    print(
        "{0} - invalid chroot format, must be '{release}-{version}-{arch}'."
            .format(chroot_name))


def print_already_exists(chroot_name):
    print("{0} - already exists.".format(chroot_name))


def print_doesnt_exist(chroot_name):
    print("{0} - chroot doesn\"t exist.".format(chroot_name))


def create_chroot(chroot_names, branch=None, activated=True):
    """Creates a mock chroot in DB"""
    for chroot_name in chroot_names:
        if not branch:
            branch = chroot_to_branch(chroot_name)
        branch_object = coprs_logic.BranchesLogic.get_or_create(branch)
        try:
            chroot = coprs_logic.MockChrootsLogic.add(chroot_name)
            chroot.distgit_branch = branch_object
            chroot.is_active = activated
            db.session.commit()
        except exceptions.MalformedArgumentException:
            print_invalid_format(chroot_name)
        except exceptions.DuplicateException:
            print_already_exists(chroot_name)


@click.command()
@click.argument(
    "chroot_names",
    nargs=-1,
    required=True
)
@click.option(
    "--dist-git-branch", "-b", "branch",
    help="Branch name for this set of new chroots"
)
@click.option(
    "--activated/--deactivated",
    help="Activate the chroot later, manually by `alter_chroot`",
    default=True
)
def create_chroot_command(chroot_names, branch=None, activated=True):
    """Creates a mock chroot in DB"""
    return create_chroot(chroot_names, branch, activated)
