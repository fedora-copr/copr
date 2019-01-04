from flask_script import Command
from coprs import db


class DropDBCommand(Command):

    """
    Delete DB
    """

    def run(self):
        db.drop_all()
