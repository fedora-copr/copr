import click
import os
import subprocess
import sys

# keep backward compat with old flask's manage.py API
map_flask_commands = {'runserver': 'run'}

def function(ctx, args):
    cmd = ctx.info_name
    arguments = ['flask-3', map_flask_commands.get(cmd, cmd)]
    arguments.extend(list(args))
    if 'PYTHONPATH' in os.environ:
        os.environ['PYTHONPATH'] += ":/usr/share/copr/coprs_frontend/"
    else:
        os.environ['PYTHONPATH'] = "/usr/share/copr/coprs_frontend/"
    os.environ['FLASK_APP'] = "coprs:app"
    sys.exit(subprocess.call(arguments))

def get_flask_wrapper_command(name):
    argument = click.Argument(['args'], nargs=-1, type=click.UNPROCESSED)
    command = click.Command(
        name,
        context_settings=dict(ignore_unknown_options=True, help_option_names=[]),
        callback=click.pass_context(function),
        params=[argument],
        help='Wrapper around "/bin/flask-3 {}" command'.format(
            map_flask_commands.get(name, name)),
    )
    if hasattr(command, 'hidden'):
        # available on f30+ only (click v7.0)
        command.hidden = name in map_flask_commands
    return command
