import argparse
import os
import subprocess
import click

@click.command(context_settings=dict(
    ignore_unknown_options=True,
))
@click.argument("arguments", nargs=-1, type=click.UNPROCESSED)
@click.option("--coverage/--no-coverage",
    default=False
)

def test(coverage, arguments):
    """
    Runs tests
    """
    os.environ["COPRS_ENVIRON_UNITTEST"] = "1"
    if not (("COPR_CONFIG" in os.environ) and os.environ["COPR_CONFIG"]):
        os.environ["COPR_CONFIG"] = "/etc/copr/copr_unit_test.conf"

    if 'PYTHONPATH' in os.environ:
        os.environ['PYTHONPATH'] = os.environ['PYTHONPATH'] + ':.'
    else:
        os.environ['PYTHONPATH'] = '.'

    additional_args = list(arguments)

    if coverage:
        additional_args.extend([
            '--cov-report', 'term-missing', '--cov', 'coprs'
        ])

    return subprocess.call(["/usr/bin/python3", "-m", "pytest"] + additional_args)
