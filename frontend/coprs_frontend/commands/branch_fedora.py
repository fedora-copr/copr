import click
from coprs.logic import coprs_logic

from commands.create_chroot import create_chroot_function
from commands.rawhide_to_release import rawhide_to_release_function


@click.command()
@click.argument(
    "fedora_version",
    type=int
)
@click.option(
    "--dist-git-branch", "-b", "branch",
    help="Branch name for this set of new chroots"
)
def branch_fedora(fedora_version, branch=None):
    """
    Branch fedora-rawhide-* chroots to fedora-N* and execute rawhide-to-release
    on them
    """
    rawhide_chroots = coprs_logic.MockChrootsLogic.get_from_name(
        "fedora-rawhide",
        active_only=True,
        noarch=True).all()

    chroot_pairs = {
        'fedora-{}-{}'.format(fedora_version, rch.arch):
        'fedora-rawhide-{}'.format(rch.arch)
        for rch in rawhide_chroots
    }

    create_chroot_function(chroot_pairs.keys(), branch, True)

    for new_chroot, rawhide_chroot in chroot_pairs.items():
        rawhide_to_release_function(rawhide_chroot, new_chroot)
