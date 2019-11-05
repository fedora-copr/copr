import click
import os
import subprocess
import sys

"""
Runs local server
"""
@click.command(context_settings=dict(
    ignore_unknown_options=True,
))
@click.argument(
    'args',
    nargs=-1,
    type=click.UNPROCESSED
)
def runserver(args):
    arguments = ['flask-3', 'run']
    arguments.extend(list(args))
    if 'PYTHONPATH' in os.environ:
        os.environ['PYTHONPATH'] += ":/usr/share/copr/coprs_frontend/"
    else:
        os.environ['PYTHONPATH'] = "/usr/share/copr/coprs_frontend/"
    os.environ['FLASK_APP'] = "coprs:app"
    subprocess.check_call(arguments)
