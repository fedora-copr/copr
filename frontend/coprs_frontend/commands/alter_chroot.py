import datetime
import click

from coprs import db_session_scope
from coprs import app
from coprs import exceptions
from coprs.logic import coprs_logic
from commands.create_chroot import print_invalid_format, print_doesnt_exist


@click.command()
@click.argument(
    "chroot_names",
    nargs=-1
)
@click.option(
    "--action", "-a", "action",
    help="Action to take - currently activate or deactivate",
    required=True,
    type=click.Choice(["activate", "deactivate", "eol"])
)
def alter_chroot(chroot_names, action):
    """Activates or deactivates a chroot"""
    func_alter_chroot(chroot_names, action)

def func_alter_chroot(chroot_names, action):
    """
    A library-like variant of 'alter_chroot', used for unit-testing purposes.
    """
    activate = (action == "activate")

    delete_after_days = app.config["DELETE_EOL_CHROOTS_AFTER"]
    delete_after_timestamp = datetime.datetime.now() + datetime.timedelta(delete_after_days)

    for chroot_name in chroot_names:
        try:
            with db_session_scope():
                mock_chroot = coprs_logic.MockChrootsLogic.edit_by_name(
                    chroot_name, activate)

                if action == "deactivate":
                    continue

                for copr_chroot in mock_chroot.copr_chroots:
                    # Don't touch unclicked chroots
                    if copr_chroot.deleted:
                        continue

                    if activate:
                        # reset EOL policy after re-activation
                        copr_chroot.delete_after = None
                        copr_chroot.delete_notify = None
                    else:
                        if copr_chroot.deleted:
                            # If the chroot was unclicked (deleted) from
                            # a project, we don't want to run the whole EOL
                            # machinery. The `delete_after` should be already
                            # set and we want to keep it as is
                            assert copr_chroot.delete_after
                            continue
                        copr_chroot.delete_after = delete_after_timestamp

        except exceptions.MalformedArgumentException:
            print_invalid_format(chroot_name)
        except exceptions.NotFoundException:
            print_doesnt_exist(chroot_name)
