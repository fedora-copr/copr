from coprs import db
from coprs import models
from flask_script import Command, Option, Group


class AlterUserCommand(Command):

    def run(self, name, **kwargs):
        user = models.User.query.filter(
            models.User.username == name).first()
        if not user:
            print("No user named {0}.".format(name))
            return

        if kwargs["admin"]:
            user.admin = True
        if kwargs["no_admin"]:
            user.admin = False
        if kwargs["proven"]:
            user.proven = True
        if kwargs["no_proven"]:
            user.proven = False
        if kwargs["proxy"]:
            user.proxy = True
        if kwargs["no_proxy"]:
            user.proxy = False

        db.session.add(user)
        db.session.commit()

    option_list = (
        Option("name"),
        Group(
            Option("--admin",
                   action="store_true"),
            Option("--no-admin",
                   action="store_true"),
            exclusive=True
        ),
        Group(
            Option("--proven",
                   action="store_true"),
            Option("--no-proven",
                   action="store_true"),
            exclusive=True
        ),
        Group(
            Option("--proxy",
                   action="store_true"),
            Option("--no-proxy",
                   action="store_true"),
            exclusive=True
        )
    )
