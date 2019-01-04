from flask_script import Command, Option
from coprs import db
from coprs import models
from coprs.views.misc import create_user_wrapper


class AddUserCommand(Command):

    """
    You should not use regularly as that user will not be related to FAS account.
    This should be used only for testing or adding special accounts e.g. proxy user.
    """

    def run(self, name, mail, **kwargs):
        user = models.User.query.filter(models.User.username == name).first()
        if user:
            print("User named {0} already exists.".format(name))
            return

        user = create_user_wrapper(name, mail)
        if kwargs["api_token"]:
            user.api_token = kwargs["api_token"]
        if kwargs["api_login"]:
            user.api_token = kwargs["api_login"]

        db.session.add(user)
        db.session.commit()

    option_list = (
        Option("name"),
        Option("mail"),
        Option("--api_token", default=None, required=False),
        Option("--api_login", default=None, required=False),
    )
