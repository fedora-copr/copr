#-*- coding: UTF-8 -*-

"""
Function actually doing the work of calling the API and handling the
output.
"""

import ConfigParser
import datetime
import json
import os
import re
import requests
import sys
import time

import copr_exceptions


def _get_data(req, user, copr=None):
    """ Wrapper around response from server

    checks data and raises a CoprCliRequestException with nice error message
    or CoprCliUnknownResponseException in case of some some error. 
    Otherwise return json object.
    """
    if "<title>Sign in Coprs</title>" in req.text:
        raise copr_exceptions.CoprCliRequestException("Invalid API token\n")
        return

    if req.status_code == 404:
        if copr is None:
            raise copr_exceptions.CoprCliRequestException(
                        "User {0} is unknown.\n".format(user["username"]))
        else:
            raise copr_exceptions.CoprCliRequestException(
                        "Project {0}/{1} not found.\n".format(
                        user["username"], copr))
    try:
        output = json.loads(req.text)
    except ValueError:
        raise copr_exceptions.CoprCliUnknownResponseException(
                    "Unknown response from the server.")
    if req.status_code != 200:
        raise copr_exceptions.CoprCliRequestException(output["error"])
    return output


def get_user():
    """ Retrieve the user information from the config file. """
    config = ConfigParser.ConfigParser()
    if not config.read(
            os.path.join(os.path.expanduser("~"), ".config", "copr")):
        raise copr_exceptions.CoprCliNoConfException(
            "No configuration file '~/.config/copr' found. "
            "See man copr-cli for more information")
    try:
        username = config.get("copr-cli", "username", None)
        login = config.get("copr-cli", "login", None)
        token = config.get("copr-cli", "token", None)
    except ConfigParser.Error as err:
        raise copr_exceptions.CoprCliConfigException(
            "Bad configuration file: {0}".format(err))
    return {"username": username, "token": token, "login": login}


def get_api_url():
    """ Retrieve the user information from the config file. """
    config = ConfigParser.ConfigParser()
    config.read(
        os.path.join(os.path.expanduser("~"), ".config", "copr")
    )

    # Default copr_url:
    copr_url = "http://copr.fedoraproject.org/"
    if (config.has_section("copr-cli") and
            config.has_option("copr-cli", "copr_url")):

        copr_url = config.get("copr-cli", "copr_url")
    return "{0}/api".format(copr_url)


def listcoprs(username=None):
    """ List all the copr of a user. """
    user = {}
    if not username:
        user = get_user()
        del(user["token"])

    if username:
        user["username"] = username

    copr_api_url = get_api_url()
    url = "{0}/coprs/{1}/".format(copr_api_url, user["username"])

    req = requests.get(url)
    output = _get_data(req, user)
    if output is None:
        return
    elif "repos" in output:
        PAD = " " * 2
        if output["repos"]:
            for repo in output["repos"]:
                print("Name: {0}".format(repo["name"]))

                if "description" in repo:
                    desc = repo["description"]
                    print(PAD + "Description: {0}".format(desc))

                if "yum_repos" in repo:
                    yum_repos = repo["yum_repos"]
                    print(PAD + "Yum repo(s):")
                    for k in sorted(yum_repos.keys()):
                        print(PAD * 2 + "{0}: {1}".format(k, yum_repos[k]))

                if "additional_repos" in repo:
                    add_repos = repo["additional_repos"]
                    print(PAD + "Additional repos: {0}".format(add_repos))

                if "instructions" in repo:
                    instructions = repo["instructions"]
                    print(PAD + "Instructions: {0}".format(instructions))
        else:
            print("No copr retrieved for user: '{0}'".format(
                user["username"]))
    else:
        print("Un-expected data returned, please report this issue")


def create(name, chroots=[], description=None, instructions=None,
           repos=None, initial_pkgs=None):
    """ Create a new copr. """
    if chroots is None:
        raise copr_exceptions.CoprCliRequestException(
                    "At least one chroot must be selected")

    user = get_user()
    copr_api_url = get_api_url()
    URL = "{0}/coprs/{1}/new/".format(copr_api_url, user["username"])

    if type(repos) == list():
        repos = " ".join(repos)

    if type(initial_pkgs) == list():
        initial_pkgs = " ".join(initial_pkgs)

    data = {"name": name,
            "repos": repos,
            "initial_pkgs": initial_pkgs,
            "description": description,
            "instructions": instructions
            }
    for chroot in chroots:
        data[chroot] = "y"

    req = requests.post(URL,
                        auth=(user["login"], user["token"]),
                        data=data)
    output = _get_data(req, user)
    if output is not None:
        print(output["message"])


def _fetch_status(build_id):
    user = get_user()
    copr_api_url = get_api_url()
    URL = "{0}/coprs/build_status/{1}/".format(
        copr_api_url,
        build_id)

    req = requests.get(URL, auth=(user["login"], user["token"]))
    output = _get_data(req, user)
    if output is None:
        return (False, "Error occurred.")
    elif "status" in output:
        return (True, output["status"])
    else:
        return (False, output["error"])


def status(build_id):
    """ Return status of build """
    (ret, value) = _fetch_status(build_id)
    print(value)

def cancel(build_id):
    """ Cancel specified build_id """
    user = get_user()
    copr_api_url = get_api_url()
    #/coprs/rhscl/nodejs010/cancel_build/4060/
    URL = "{0}/coprs/cancel_build/{1}/".format(
        copr_api_url,
        build_id)
    req = requests.post(URL, auth=(user["login"], user["token"]))
    output = _get_data(req, user)
    if output is None:
        return (False, "Error occurred.")
    elif "status" in output:
        return (True, output["status"])
    else:
        return (False, output["error"])

def build(copr, pkgs, memory, timeout, wait=True, result=None, chroots=None):
    """ Build a new package into a given copr.

    Result is dictionary where is returned "errmsg" in case of error.
    And "id" and "status" otherwise.
    """
    user = get_user()
    username = user["username"]

    # if you specify copr as username/foo, retrieve and cut username
    m = re.match(r"(.+)/(.+)", copr)
    if m:
        username = m.group(1)
        copr = m.group(2)

    copr_api_url = get_api_url()
    URL = "{0}/coprs/{1}/{2}/new_build/".format(
        copr_api_url,
        username,
        copr)

    data = {"pkgs": " ".join(pkgs),
            "memory": memory,
            "timeout": timeout
            }

    if chroots is not None:
        for chroot in chroots:
            data[chroot] = "y"

    req = requests.post(URL,
                        auth=(user["login"], user["token"]),
                        data=data)
    output = _get_data(req, user, copr)
    if output is None:
        return
    else:
        print(output["message"])

    if wait:
        print("{0} builds were added.".format(len(output["ids"])))
        print("Watching builds (this may be safely interrupted)...")
        prevstatus = {}
        for id in output["ids"]:
            prevstatus[id] = None
            if result is not None:
                result[id] = {}
        try:
            while True:
                for id in output["ids"]:
                    (ret, status) = _fetch_status(id)
                    if not ret:
                        errmsg = "Build {1}: Unable to get build status: {0}".format(status,id)
                        print errmsg
                        if result is not None:
                            result[id]['errmsg'] = errmsg
                        return False

                    now = datetime.datetime.now()
                    if prevstatus[id] != status:
                        print("{0} Build {2}: {1}".format(now.strftime("%H:%M:%S"), status, id))
                        prevstatus[id] = status

                    if status in ["succeeded", "failed", "canceled"]:
                        if result is not None:
                            result[id]['status'] = status
                        output["ids"].remove(id)

                if not output["ids"]:
                    return True

                time.sleep(60)

        except KeyboardInterrupt:
            pass

    return True
