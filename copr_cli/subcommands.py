#-*- coding: UTF-8 -*-

"""
Function actually doing the work of calling the API and handling the
output.
"""

import os
import sys
import time
import json
import datetime
import ConfigParser

import requests

import copr_exceptions


def get_user():
    """ Retrieve the user information from the config file. """
    config = ConfigParser.ConfigParser()
    if not config.read(
            os.path.join(os.path.expanduser('~'), '.config', 'copr')):
        raise copr_exceptions.CoprCliNoConfException(
            'No configuration file "~/.config/copr" found.')
    try:
        username = config.get('copr-cli', 'username', None)
        login = config.get('copr-cli', 'login', None)
        token = config.get('copr-cli', 'token', None)
    except ConfigParser.Error, err:
        raise copr_exceptions.CoprCliConfigException(
            'Bad configuration file: %s' % err)
    return {'username': username, 'token': token, 'login': login}


def get_api_url():
    """ Retrieve the user information from the config file. """
    config = ConfigParser.ConfigParser()
    config.read(
        os.path.join(os.path.expanduser('~'), '.config', 'copr')
    )

    # Default copr_url:
    copr_url = 'http://copr-fe.cloud.fedoraproject.org/'
    if config.has_section('copr-cli'):
        copr_url = config.get('copr-cli', 'copr_url')
    return '%s/api' % copr_url


def listcoprs(username=None):
    """ List all the copr of a user. """
    user = {}
    if not username:
        user = get_user()
        del(user['token'])

    if username:
        user['username'] = username

    copr_api_url = get_api_url()
    url = '{0}/coprs/{1}/'.format(copr_api_url, user['username'])

    req = requests.get(url)

    if '<title>Sign in Coprs</title>' in req.text:
        print 'Invalid API token'
        return

    output = json.loads(req.text)
    if req.status_code != 200:
        print 'Something went wrong:\n {0}'.format(output['error'])
        return

    output = json.loads(req.text)

    if 'repos' in output:
        if output['repos']:
            for repo in output['repos']:
                print 'Name: {0}'.format(repo['name'])

                if 'description' in repo:
                    desc = repo['description']
                    print ' ' * 5, 'Description: {0}'.format(desc)

                if 'yum_repos' in repo:
                    yum_repos = repo['yum_repos']
                    print ' ' * 5, 'Yum repo: {0}'.format(yum_repos)

                if 'additional_repos' in repo:
                    add_repos = repo['additional_repos']
                    print ' ' * 5, 'Additional repos: {0}'.format(add_repos)

                if 'instructions' in repo:
                    instructions = repo['instructions']
                    print ' ' * 5, 'Instructions: {0}'.format(instructions)
        else:
            print 'No copr retrieved for user: "{0}"'.format(
                user['username'])
    else:
        print 'Un-expected data returned, please report this issue'


def create(name, chroots=[], description=None, instructions=None,
           repos=None, initial_pkgs=None):
    """ Create a new copr. """
    if chroots is None:
        print "Error: At least one chroot must be selected"
        sys.exit(1)
    user = get_user()
    copr_api_url = get_api_url()
    URL = '{0}/coprs/{1}/new/'.format(copr_api_url, user['username'])

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
                        auth=(user['login'], user['token']),
                        data=data)
    if '<title>Sign in Coprs</title>' in req.text:
        print 'Invalid API token'
        return

    output = json.loads(req.text)
    if req.status_code != 200:
        print 'Something went wrong:\n {0}'.format(output['error'])
    else:
        print output['message']


def _fetch_status(build_id):
    user = get_user()
    copr_api_url = get_api_url()
    URL = '{0}/coprs/build_status/{1}/'.format(
        copr_api_url,
        build_id)

    req = requests.get(URL, auth=(user['login'], user['token']))

    if '<title>Sign in Coprs</title>' in req.text:
        print('Invalid API token')
        return

    output = json.loads(req.text)
    if req.status_code != 200:
        return (False, output['error'])
    else:
        return (True, output['status'])


def status(build_id):
    """ Return status of build """
    (ret, value) = _fetch_status(build_id)
    print(value)


def build(copr, pkgs, memory, timeout, wait=True):
    """ Build a new package into a given copr. """
    user = get_user()
    copr_api_url = get_api_url()
    URL = '{0}/coprs/{1}/{2}/new_build/'.format(
        copr_api_url,
        user['username'],
        copr)

    data = {'pkgs': ' '.join(pkgs),
            'memory': memory,
            'timeout': timeout
            }

    req = requests.post(URL,
                        auth=(user['login'], user['token']),
                        data=data)

    if '<title>Sign in Coprs</title>' in req.text:
        print 'Invalid API token'
        return

    output = json.loads(req.text)
    if req.status_code != 200:
        print 'Something went wrong:\n {0}'.format(output['error'])
        return False
    else:
        print output['message']

    if wait:
        print("Build ID: {0}".format(output['id']))
        print("Watching build (this may be safely interrupted)...")
        prevstatus = None
        try:
            while True:
                (ret, status) = _fetch_status(output['id'])
                if not ret:
                    print("Unable to get build status: {0}".format(status))
                    return False

                now = datetime.datetime.now()
                if prevstatus != status:
                    print("{0} {1}".format(now.strftime('%H:%M:%S'), status))
                    prevstatus = status

                if status in ['succeeded', 'failed']:
                    return True

                time.sleep(60)

        except KeyboardInterrupt:
            pass

    return True
