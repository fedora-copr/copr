import argparse
import os
import subprocess
from flask_script import Command, Option


class TestCommand(Command):

    def run(self, coverage, test_args):
        os.environ["COPRS_ENVIRON_UNITTEST"] = "1"
        if not (("COPR_CONFIG" in os.environ) and os.environ["COPR_CONFIG"]):
            os.environ["COPR_CONFIG"] = "/etc/copr/copr_unit_test.conf"

        if 'PYTHONPATH' in os.environ:
            os.environ['PYTHONPATH'] = os.environ['PYTHONPATH'] + ':.'
        else:
            os.environ['PYTHONPATH'] = '.'

        additional_args = test_args

        if coverage:
            additional_args.extend([
                '--cov-report', 'term-missing', '--cov', 'coprs'
            ])

        return subprocess.call(["/usr/bin/python3", "-m", "pytest"] + additional_args)

    option_list = (
        Option("-a",
               dest="test_args",
               nargs=argparse.REMAINDER),
        Option("--coverage",
               dest="coverage",
               required=False,
               action='store_true',
               default=False),
    )
