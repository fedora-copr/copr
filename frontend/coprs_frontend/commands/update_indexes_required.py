import sys
import click
from coprs.whoosheers import WhoosheeStamp

@click.command()
def update_indexes_required():
    """
    Is whooshee indexes rebuild required?
    """
    valid = WhoosheeStamp.is_valid()
    print("no" if valid else "yes")
    sys.exit(int(not valid))
