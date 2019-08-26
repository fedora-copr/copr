import sys
from flask_script import Command
from coprs.whoosheers import WhoosheeStamp


class UpdateIndexesRequiredCommand(Command):
    """
    Is whooshee indexes rebuild required?
    """

    def run(self):
        valid = WhoosheeStamp.is_valid()
        print("no" if valid else "yes")
        sys.exit(int(not valid))
