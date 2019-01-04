from coprs import models
from coprs.logic import users_logic
from flask_script import Command, Option


class DumpUserCommand(Command):

    def run(self, username):
        user = models.User.query.filter(models.User.username == username).first()
        if not user:
            print("There is no user named {0}.".format(username))
            return 1
        dumper = users_logic.UserDataDumper(user)
        print(dumper.dumps(pretty=True))

    option_list = (
        Option("username"),
    )
