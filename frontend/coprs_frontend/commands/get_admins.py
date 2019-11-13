import click
from coprs import models

@click.command()
def get_admins():
    """
    Display list of admins
    """
    for u in models.User.query.filter(models.User.admin == True).all():
        print(u.username)
