import click
from coprs import db
from coprs.logic.coprs_logic import MockChrootsLogic


@click.command()
@click.option(
    "--chroot", "-r", "chrootname",
    required=True
)
@click.option(
    "--comment", "-c", "comment",
    required=True
)
def comment_chroot(chrootname, comment):
    """
    Add comment to a mock_chroot.
    """
    chroot = MockChrootsLogic.get_from_name(chrootname).first()
    if not chroot:
        print("There is no mock chroot named {0}.".format(chrootname))
        return
    chroot.comment = comment
    db.session.commit()
