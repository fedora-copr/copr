import click
from coprs import db
from coprs import models

@click.command()
@click.argument("name", required=True)
@click.option('--mail', required=False)
@click.option('--admin/--no-admin', default=False)
@click.option('--proven/--no-proven', default=False)
@click.option("--api-token", "-t", required=False)
@click.option("--api-login", "-l", required=False)
def alter_user(name, mail, admin, proven, api_token=None, api_login=None):
    """
    Alter user data
    """
    user = models.User.query.filter(
        models.User.username == name).first()
    if not user:
        print("No user named {0}.".format(name))
        return

    user.admin = admin
    user.proven = proven

    if mail:
        user.mail = mail
    if api_token:
        user.api_token = api_token
    if api_login:
        user.api_login = api_login

    db.session.add(user)
    db.session.commit()
