#!/usr/bin/python -tt
#-*- coding: UTF-8 -*-

import logging
import sys


import cliff.app
import cliff.commandmanager
from cliff.commandmanager import CommandManager

__version__ = '0.1.0'
__description__ = "CLI tool to run copr"

copr_url = 'http://copr-fe.cloud.fedoraproject.org/'
copr_api_url = '{0}/api'.format(copr_url)


class CoprCli(cliff.app.App):

    log = logging.getLogger(__name__)

    def __init__(self):
        manager = cliff.commandmanager.CommandManager('copr_cli.subcommands')
        super(CoprCli, self).__init__(
            description=__description__,
            version=__version__,
            command_manager=manager,
        )
        requests_log = logging.getLogger("requests")
        requests_log.setLevel(logging.WARN)

    def initialize_app(self, argv):
        self.log.debug('initialize_app')

    def prepare_to_run_command(self, cmd):
        self.log.debug('prepare_to_run_command %s', cmd.__class__.__name__)

    def clean_up(self, cmd, result, err):
        self.log.debug('clean_up %s', cmd.__class__.__name__)
        if err:
            self.log.debug('got an error: %s', err)

    # Overload run_subcommand to gracefully handle unknown commands.
    def run_subcommand(self, argv):
        try:
            self.command_manager.find_command(argv)
        except ValueError as e:
            if "Unknown command" in str(e):
                print "%r is an unknown command" % ' '.join(argv)
                print "Try \"copr -h\""
                sys.exit(1)
            else:
                raise

        return super(CoprCli, self).run_subcommand(argv)


def main(argv=sys.argv[1:]):
    """ Main function """
    myapp = CoprCli()
    return myapp.run(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
    #add_copr('test2', 'fedora-rawhide-x86_64',
        #description='Test repos #2')
    #list_copr()
