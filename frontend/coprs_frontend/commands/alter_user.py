import click
from coprs import db
from coprs import models
from coprs.logic.api_logic import APILogic

@click.command()
@click.argument("name", required=True)
@click.option('--mail', required=False)
@click.option('--admin/--no-admin', default=False)
@click.option('--proven/--no-proven', default=False)
@click.option("--api-token", "-t", required=False)
@click.option("--api-login", "-l", required=False)
@click.option("--api-generate", is_flag=True)
def alter_user(name, mail, admin, proven, api_token=None, api_login=None,
               api_generate=False):
    """
    Alter user data
    """
    if api_generate and (api_token or api_login):
        raise click.UsageError(
            "argument --api-generate: not allowed with arguments "
            "--api-token or --api-login."
        )

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
    if api_generate:
        APILogic.generate_api_token(user)

    db.session.add(user)
    db.session.commit()
