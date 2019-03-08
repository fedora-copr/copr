import datetime
from flask_script import Option
from coprs import db_session_scope
from coprs import app
from coprs import exceptions
from coprs.logic import coprs_logic
from commands.create_chroot import ChrootCommand


class AlterChrootCommand(ChrootCommand):

    "Activates or deactivates a chroot"

    def run(self, chroot_names, action):
        activate = (action == "activate")
        for chroot_name in chroot_names:
            try:
                with db_session_scope():
                    mock_chroot = coprs_logic.MockChrootsLogic.edit_by_name(
                        chroot_name, activate)

                    if action != "eol":
                        continue

                    for copr_chroot in mock_chroot.copr_chroots:
                        delete_after_days = app.config["DELETE_EOL_CHROOTS_AFTER"] + 1
                        delete_after_timestamp = datetime.datetime.now() + datetime.timedelta(delete_after_days)
                        # Workarounding an auth here
                        coprs_logic.CoprChrootsLogic.update_chroot(copr_chroot.copr.user, copr_chroot,
                                                                   delete_after=delete_after_timestamp)
            except exceptions.MalformedArgumentException:
                self.print_invalid_format(chroot_name)
            except exceptions.NotFoundException:
                self.print_doesnt_exist(chroot_name)

    option_list = ChrootCommand.option_list + (
        Option("--action",
               "-a",
               dest="action",
               help="Action to take - currently activate or deactivate",
               choices=["activate", "deactivate", "eol"],
               required=True),
    )
