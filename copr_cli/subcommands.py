#-*- coding: UTF-8 -*-

import ConfigParser
import json
import logging
import requests
import os
import sys

import cliff.lister
import cliff.show

from cliff.command import Command

from main import copr_api_url


def set_user():
    """ Retrieve the user information from the config file. """
    config = ConfigParser.ConfigParser()
    config.read(os.path.join(os.path.expanduser('~'), '.config',
                'copr'))
    username = config.get('copr-cli', 'username', None)
    token = config.get('copr-cli', 'token', None)
    return {'username': username, 'token': token}


class List(cliff.lister.Lister):
    """ List all the copr of a user. """

    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(type(self), self).get_parser(prog_name)
        parser.add_argument("username", nargs='?')
        return parser

    def take_action(self, args):
        user = set_user()

        if args.username:
            user['username'] = args.username
        URL = '{0}/owned/'.format(copr_api_url)
        req = requests.get(URL, params=user)
        output = json.loads(req.text)
        if 'repos' in output:
            if output['repos']:
                columns = ['name', 'description', 'repos', 'instructions']
                values = []
                for entry in output['repos']:
                    values.append([entry[key] for key in columns])
                return (columns, values)
            else:
                columns = ['output']
                values = ['No copr retrieved for user: "{0}"'.format(
                    user['username'])]
                return (columns, [values])
        else:
            columns = ['output']
            values = ['Wrong output format returned by the server']
            return (columns, [values])


class AddCopr(Command):
    """ Create a new copr. """

    log = logging.getLogger(__name__)

    def get_parser(self, prog_name):
        parser = super(type(self), self).get_parser(prog_name)
        parser.add_argument("name")
        parser.add_argument("--chroot", dest="chroots", action='append',
                            help="")
        parser.add_argument('--repo', dest='repos', action='append',
                            help="")
        parser.add_argument('--initial-pkgs', dest='initial_pkgs',
                            action='append',
                            help="")
        parser.add_argument('--description',
                            help="")
        parser.add_argument('--instructions',
                            help="")
        return parser

    def take_action(self, args):
        user = set_user()
        URL = '{0}/copr/new/'.format(copr_api_url)

        repos = None
        if args.repos:
            repos = ' '.join(args.repos)
        initial_pkgs = None
        if args.initial_pkgs:
            initial_pkgs = ' '.join(args.initial_pkgs)
        data = {'name': args.name,
                'repos': repos,
                'initial_pkgs': initial_pkgs,
                'description': args.description,
                'instructions': args.instructions
                }
        for chroot in args.chroots:
            data[chroot] = 'y'

        req = requests.post(URL,
                            auth=(user['username'], user['token']),
                            data=data)
        output = json.loads(req.text)
        if output['output'] == 'ok':
            print output['message']
        else:
            print 'Something went wrong:\n  {0}'.format(output['error'])
