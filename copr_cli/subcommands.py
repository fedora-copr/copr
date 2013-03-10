#-*- coding: UTF-8 -*-

"""
Function actually doing the work of calling the API and handling the
output.
"""

import ConfigParser
import json
import os
import sys

import requests

import copr_exceptions


def get_user():
    """ Retrieve the user information from the config file. """
    config = ConfigParser.ConfigParser()
    if not config.read(os.path.join(os.path.expanduser('~'), '.config',
                'copr')):
        raise copr_exceptions.CoprCliNoConfException(
            'No configuration file "~/.config/copr" found.')
    try:
        username = config.get('copr-cli', 'username', None)
        token = config.get('copr-cli', 'token', None)
    except ConfigParser.Error, err:
        raise copr_exceptions.CoprCliConfigException(
            'Bad configuration file: %s' % err)
    return {'username': username, 'token': token}


def get_api_url():
    """ Retrieve the user information from the config file. """
    config = ConfigParser.ConfigParser(
        {'copr_url': 'http://copr-fe.cloud.fedoraproject.org'})
    config.read(os.path.join(os.path.expanduser('~'), '.config',
                'copr'))
    copr_url = config.get('copr-cli', 'copr_url')
    return '%s/api' % copr_url


def listcoprs(username=None):
    """ List all the copr of a user. """
    user = {}
    if not username:
        user = get_user()
        del(user['token'])

    copr_api_url = get_api_url()
    url = '{0}/owned/'.format(copr_api_url)

    if username:
        user['username'] = username

    req = requests.get(url, params=user)

    if '<title>Sign in Coprs</title>' in req.text:
        print 'Invalid API token'
        return

    output = json.loads(req.text)
    if req.status_code != 200:
        print 'Something went wrong:\n {0}'.format(output['error'])
        return

    output = json.loads(req.text)
    columns = []
    values = []
    if 'repos' in output:
        if output['repos']:
            columns = ['name', 'description', 'repos', 'instructions']
            values = []
            for entry in output['repos']:
                values.append([entry[key] for key in columns])
        else:
            columns = ['output']
            values = ['No copr retrieved for user: "{0}"'.format(
                user['username'])]
    else:
        columns = ['output']
        values = ['Wrong output format returned by the server']

    def _list_to_row(values, widths):
        ''' Return a print ready version of the provided list '''
        row = []
        cnt = 0
        for item in values:
            max_width = widths[cnt]
            cnt += 1
            if not item:
                item = ''
            if cnt < len(values):
                row.append(item.ljust(max_width + 1))
            else:
                row.append(item)
        return row

    if len(columns) > 1:
        widths = {}
        cnt = 0
        for item in columns:
            widths[cnt] = len(item)
            cnt += 1
        for row in values:
            cnt = 0
            for item in row:
                if not item:
                    item = ''
                widths[cnt] = max(widths[cnt], len(item))
                cnt += 1

        headers = '|'.join(_list_to_row(columns, widths))
        print headers
        print '-' * len(headers)
        for row in values:
            print "|".join(_list_to_row(row, widths))

    else:
        max_width = len(values[0])
        headers = columns[0]
        print headers
        print "-"*len(headers)
        print values[0]


def create(name, chroots=[], description=None, instructions=None,
           repos=None, initial_pkgs=None):
    """ Create a new copr. """
    user = get_user()
    copr_api_url = get_api_url()
    URL = '{0}/copr/new/'.format(copr_api_url)

    repos = None
    if type(repos) == list():
        repos = ' '.join(repos)
    initial_pkgs = None
    if type(initial_pkgs) == list():
        initial_pkgs = ' '.join(initial_pkgs)
    data = {'name': name,
            'repos': repos,
            'initial_pkgs': initial_pkgs,
            'description': description,
            'instructions': instructions
            }
    for chroot in chroots:
        data[chroot] = 'y'

    req = requests.post(URL,
                        auth=(user['username'], user['token']),
                        data=data)
    if '<title>Sign in Coprs</title>' in req.text:
        print 'Invalid API token'
        return

    output = json.loads(req.text)
    if req.status_code != 200:
        print 'Something went wrong:\n {0}'.format(output['error'])
    else:
        print output['message']


def build(copr, pkgs, memory, timeout):
    """ Build a new package into a given copr. """
    user = get_user()
    copr_api_url = get_api_url()
    URL = '{0}/coprs/detail/{1}/{2}/new_build/'.format(
        copr_api_url,
        user['username'],
        copr)

    data = {'pkgs': ' '.join(pkgs),
            'memory': memory,
            'timeout': timeout
            }

    req = requests.post(URL,
                        auth=(user['username'], user['token']),
                        data=data)

    if '<title>Sign in Coprs</title>' in req.text:
        print 'Invalid API token'
        return

    output = json.loads(req.text)
    if req.status_code != 200:
        print 'Something went wrong:\n {0}'.format(output['error'])
    else:
        print output['message']
