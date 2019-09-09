from flask_script import Command, Option
from coprs import db
from coprs.logic.coprs_logic import MockChrootsLogic


class CommentChrootCommand(Command):

    """
    Add comment to a mock_chroot.
    """

    def run(self, chrootname, comment):
        chroot = MockChrootsLogic.get_from_name(chrootname).first()
        if not chroot:
            print("There is no mock chroot named {0}.".format(chrootname))
            return
        chroot.comment = comment
        db.session.commit()

    option_list = (
        Option("chrootname"),
        Option("comment"),
    )
