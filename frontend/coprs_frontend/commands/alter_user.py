import click
from coprs import db
from coprs import models

@click.command()
@click.argument("name", required=True)
@click.option('--admin/--no-admin', default=False)
@click.option('--proven/--no-proven', default=False)
@click.option('--proxy/--no-proxy', default=False)
def alter_user(name, admin, proven, proxy):
    user = models.User.query.filter(
        models.User.username == name).first()
    if not user:
        print("No user named {0}.".format(name))
        return

    user.admin = admin
    user.proven = proven
    user.proxy = proxy

    db.session.add(user)
    db.session.commit()
