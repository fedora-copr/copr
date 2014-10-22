__author__ = 'vgologuz'

import os
import subprocess

from copr.client import CoprClient


def createrepo_unsafe(path, lock=None):
    """
        Run createrepo_c on the given path

        Warning! This function doesn't check user preferences.
        In most cases use `createrepo(...)`

    :param string path: target location to create repo
    :param lock: [optional]
    :return tuple: (return_code,  stdout, stderr)
    """

    comm = ['/usr/bin/createrepo_c', '--database', '--ignore-lock']
    if os.path.exists(path + '/repodata/repomd.xml'):
        comm.append("--update")
    if "epel-5" in path:
        # this is because rhel-5 doesn't know sha256
        comm.extend(['-s', 'sha', '--checksum', 'md5'])
    comm.append(path)

    if lock:
        with lock.acquire():
            cmd = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = cmd.communicate()
    else:
        cmd = subprocess.Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = cmd.communicate()

    return cmd.returncode, out, err


def get_auto_createrepo_status(front_url, username, projectname):
    client = CoprClient({"copr_url": front_url})
    result = client.get_project_details(projectname, username)
    if "auto_createrepo" in result.data:
        return bool(result.data["auto_createrepo"])
    else:
        return True


def createrepo(path, front_url, username, projectname, lock=None):
    # TODO: add means of logging

    if get_auto_createrepo_status(front_url, username, projectname):
        createrepo_unsafe(path, lock)


