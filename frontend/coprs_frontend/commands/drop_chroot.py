import click

from coprs import exceptions
from coprs import db
from coprs.logic import coprs_logic
from commands.create_chroot import print_invalid_format
from commands.create_chroot import print_doesnt_exist


@click.command()
@click.option(
    "--chroot", "-r", "chroot_names",
    help="Chroot name, e.g. fedora-18-x86_64.",
    multiple=True
)
def drop_chroot(chroot_names):
    """Deactivates a chroot"""
    for chroot_name in chroot_names:
        try:
            coprs_logic.MockChrootsLogic.delete_by_name(chroot_name)
            db.session.commit()
        except exceptions.MalformedArgumentException:
            print_invalid_format(chroot_name)
        except exceptions.NotFoundException:
            print_doesnt_exist(chroot_name)
