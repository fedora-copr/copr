from coprs import db
import click


@click.command()
def drop_db():
    """
    Delete DB
    """
    confirmation = "yes, I want to delete everything from database"
    inp = input("Whoa! This command will delete everything from database! "
                f"If you want to delete database, please write '{confirmation}'")
    if inp != confirmation:
        click.echo(f"Input doesn't match '{confirmation}'. Aborting...")
        return

    db.drop_all()
