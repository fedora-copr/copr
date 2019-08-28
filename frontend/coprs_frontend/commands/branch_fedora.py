from flask_script import Command, Option
from coprs.logic import coprs_logic

from commands.create_chroot import CreateChrootCommand
from commands.rawhide_to_release import RawhideToReleaseCommand


class BranchFedoraCommand(Command):
    """
    Branch fedora-rawhide-* chroots to fedora-N* and execute rawhide_to_release
    on them
    """

    option_list = [
        Option("fedora_version",
               help="The version of Fedora to branch Rawhide into, e.g. 32",
               type=int),
        Option(
            "--dist-git-branch",
            "-b",
            dest="branch",
            help="Branch name for this set of new chroots"),
    ]

    def run(self, fedora_version, branch=None):
        rawhide_chroots = coprs_logic.MockChrootsLogic.get_from_name(
            "fedora-rawhide",
            active_only=True,
            noarch=True).all()

        chroot_pairs = {
            'fedora-{}-{}'.format(fedora_version, rch.arch):
            'fedora-rawhide-{}'.format(rch.arch)
            for rch in rawhide_chroots
        }

        c_cmd = CreateChrootCommand()
        c_cmd.run(chroot_pairs.keys(), branch, True)

        r2r_cmd = RawhideToReleaseCommand()
        for new_chroot, rawhide_chroot in chroot_pairs.items():
            r2r_cmd.run(rawhide_chroot, new_chroot)
