import os
import subprocess
from subprocess import Popen, PIPE

from exceptions import CreateRepoError
from shlex import split

from backend.helpers import BackendConfigReader, get_redis_logger
opts = BackendConfigReader().read()

log = get_redis_logger(opts, "createrepo", "actions")

from .helpers import get_auto_createrepo_status

# todo: add logging here

def run_cmd_unsafe(comm_str, lock=None):
    log.info("Running command: {}".format(comm_str))
    comm = split(comm_str)
    try:
        # # todo: replace with file lock on target dir
        if lock:
            with lock:
                cmd = Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out, err = cmd.communicate()
        else:
            cmd = Popen(comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = cmd.communicate()
    except Exception as err:
        raise CreateRepoError(msg="Failed to execute: {}".format(err), cmd=comm_str)

    if cmd.returncode != 0:
        raise CreateRepoError(msg="exit code != 0",
                              cmd=comm_str, exit_code=cmd.returncode,
                              stdout=out, stderr=err)
    return out


def createrepo_unsafe(path, lock=None, dest_dir=None, base_url=None):
    """
        Run createrepo_c on the given path

        Warning! This function doesn't check user preferences.
        In most cases use `createrepo(...)`

    :param string path: target location to create repo
    :param lock: [optional]
    :param str dest_dir: [optional] relative to path location for repomd, in most cases
        you should also provide base_url.
    :param str base_url: optional parameter for createrepo_c, "--baseurl"

    :return tuple: (return_code,  stdout, stderr)
    """

    comm = ['/usr/bin/createrepo_c', '--database', '--ignore-lock']
    if os.path.exists(path + '/repodata/repomd.xml'):
        comm.append("--update")
    if "epel-5" in path:
        # this is because rhel-5 doesn't know sha256
        comm.extend(['-s', 'sha', '--checksum', 'md5'])

    if dest_dir:
        dest_dir_path = os.path.join(path, dest_dir)
        comm.extend(['--outputdir', dest_dir_path])
        if not os.path.exists(dest_dir_path):
            os.makedirs(dest_dir_path)

    if base_url:
        comm.extend(['--baseurl', base_url])

    comm.append(path)

    return run_cmd_unsafe(" ".join(map(str, comm)), lock)


APPDATA_CMD_TEMPLATE = \
    """/usr/bin/appstream-builder \
--api-version=0.8 \
--verbose \
--add-cache-id \
--max-threads=4 \
--temp-dir={packages_dir}/tmp \
--cache-dir={packages_dir}/cache \
--packages-dir={packages_dir} \
--output-dir={packages_dir}/appdata \
--basename=appstream \
--include-failed \
--min-icon-size=48 \
--enable-hidpi \
--origin={username}/{projectname}
"""
MODIFYREPO_TEMPLATE = \
    """/usr/bin/modifyrepo_c \
--no-compress \
{packages_dir}/appdata/appstream.xml.gz \
{packages_dir}/repodata
"""
MODIFYREPO_2_TEMPLATE = \
    """/usr/bin/modifyrepo_c \
--no-compress \
{packages_dir}/appdata/appstream-icons.tar.gz \
{packages_dir}/repodata
"""


def add_appdata(path, username, projectname, lock=None):
    kwargs = {
        "packages_dir": path,
        "username": username,
        "projectname": projectname
    }
    out_1 = run_cmd_unsafe(APPDATA_CMD_TEMPLATE.format(**kwargs), lock)
    out_2 = run_cmd_unsafe(MODIFYREPO_TEMPLATE.format(**kwargs), lock)
    out_3 = run_cmd_unsafe(MODIFYREPO_2_TEMPLATE.format(**kwargs), lock)
    out_4 = run_cmd_unsafe("chmod -R +rX {packages_dir}".format(**kwargs), lock)
    return "\n".join([out_1, out_2, out_3, out_4])


def createrepo(path, front_url, username, projectname,
               override_acr_flag=False, base_url=None, lock=None):
    """
        Creates repo depending on the project setting "auto_createrepo".
        When enabled creates `repodata` at the provided path, otherwise

    :param path: directory with rpms
    :param front_url: url to the copr frontend
    :param username: copr project owner username
    :param projectname: copr project name
    :param base_url: base_url to access rpms independently of repomd location
    :param Multiprocessing.Lock lock:  [optional] global copr-backend lock

    :return: tuple(returncode, stdout, stderr) produced by `createrepo_c`
    """
    # TODO: add means of logging

    base_url = base_url or ""

    acr_flag = get_auto_createrepo_status(front_url, username, projectname)
    if override_acr_flag or acr_flag:
        out_cr = createrepo_unsafe(path, lock)
        out_ad = add_appdata(path, username, projectname, lock)
        return "\n".join([out_cr, out_ad])
    else:
        return createrepo_unsafe(path, lock, base_url=base_url, dest_dir="devel")
