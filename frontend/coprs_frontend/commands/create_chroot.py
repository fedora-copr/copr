import click

from coprs import exceptions
from coprs import db
from coprs.helpers import chroot_to_branch
from coprs.logic import coprs_logic


def print_invalid_format(chroot_name):
    msg = ("{0} - invalid chroot format, "
           "must be '{{release}}-{{version}}-{{arch}}'.")
    print(msg.format(chroot_name))


def print_already_exists(chroot_name):
    print("{0} - already exists.".format(chroot_name))


def print_doesnt_exist(chroot_name):
    print("{0} - chroot doesn\"t exist.".format(chroot_name))


def create_chroot_function(chroot_names, branch=None, activated=True,
                           comment=None):
    """Creates a mock chroot in DB"""
    for chroot_name in chroot_names:
        try:
            # Just a validation that chroot name is in an expected format
            # Otherwise we get traceback when determining its branch value
            coprs_logic.MockChrootsLogic.tuple_from_name(chroot_name)

            if not branch:
                branch = chroot_to_branch(chroot_name)
            branch_object = coprs_logic.BranchesLogic.get_or_create(branch)

            chroot = coprs_logic.MockChrootsLogic.add(chroot_name)
            chroot.distgit_branch = branch_object
            chroot.is_active = activated
            chroot.comment = comment
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
    help="Activate the chroot later, manually by `alter-chroot`",
    default=True
)
@click.option(
    "--comment",
    help="Document any peculiarity about the new chroots.",
)
def create_chroot(chroot_names, branch=None, activated=True, comment=None):
    """Creates a mock chroot in DB"""
    return create_chroot_function(chroot_names, branch, activated, comment)
