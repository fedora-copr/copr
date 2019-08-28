from flask_script import Command, Option
from coprs import exceptions
from coprs import db
from coprs.helpers import chroot_to_branch
from coprs.logic import coprs_logic


class ChrootCommand(Command):

    def print_invalid_format(self, chroot_name):
        print(
            "{0} - invalid chroot format, must be '{release}-{version}-{arch}'."
                .format(chroot_name))

    def print_already_exists(self, chroot_name):
        print("{0} - already exists.".format(chroot_name))

    def print_doesnt_exist(self, chroot_name):
        print("{0} - chroot doesn\"t exist.".format(chroot_name))

    option_list = (
        Option("chroot_names",
               help="Chroot name, e.g. fedora-18-x86_64.",
               nargs="+"),
    )


class CreateChrootCommand(ChrootCommand):

    "Creates a mock chroot in DB"

    def __init__(self):
        self.option_list += (
            Option(
                "--dist-git-branch",
                "-b",
                dest="branch",
                help="Branch name for this set of new chroots"),
            Option(
                "--deactivated",
                action="store_true",
                help="Activate the chroot later, manually by `alter_chroot`"
            ),
        )

    def run(self, chroot_names, branch=None, deactivated=False):
        for chroot_name in chroot_names:
            if not branch:
                branch = chroot_to_branch(chroot_name)
            branch_object = coprs_logic.BranchesLogic.get_or_create(branch)
            try:
                chroot = coprs_logic.MockChrootsLogic.add(chroot_name)
                chroot.distgit_branch = branch_object
                chroot.is_active = not deactivated
                db.session.commit()
            except exceptions.MalformedArgumentException:
                self.print_invalid_format(chroot_name)
            except exceptions.DuplicateException:
                self.print_already_exists(chroot_name)
