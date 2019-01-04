from coprs import exceptions
from coprs import db
from coprs.logic import coprs_logic
from commands.create_chroot import ChrootCommand

class DropChrootCommand(ChrootCommand):

    "Activates or deactivates a chroot"

    def run(self, chroot_names):
        for chroot_name in chroot_names:
            try:
                coprs_logic.MockChrootsLogic.delete_by_name(chroot_name)
                db.session.commit()
            except exceptions.MalformedArgumentException:
                self.print_invalid_format(chroot_name)
            except exceptions.NotFoundException:
                self.print_doesnt_exist(chroot_name)
