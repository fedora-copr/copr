import click
from coprs import db, app
from coprs import models
from coprs.logic.users_logic import UsersLogic

@click.command()
@click.argument("name")
@click.argument("mail")
@click.option(
    "--api-token", "-t", "api_token",
    required=False
)
@click.option(
    "--api-login", "-l", "api_login",
    required=False
)
def add_user(name, mail, api_token=None, api_login=None):
    return add_user_function(name, mail, api_token, api_login)


def add_user_function(name, mail, api_token=None, api_login=None):
    """
    You should not use regularly as that user will not be related to FAS account.
    This should be used only for testing.
    """
    user = models.User.query.filter(models.User.username == name).first()
    if user:
        print("User named {0} already exists.".format(name))
        return

    user = UsersLogic.create_user_wrapper(name, mail)
    if api_token:
        user.api_token = api_token
    if api_login:
        user.api_login = api_login

    db.session.add(user)
    db.session.commit()
