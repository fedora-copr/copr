import json
import os
from subprocess import Popen, PIPE

from shlex import split
from setproctitle import getproctitle, setproctitle
from oslo_concurrency import lockutils
from copr_backend.helpers import get_redis_connection

# todo: add logging here
# from copr_backend.helpers import BackendConfigReader, get_redis_logger
# opts = BackendConfigReader().read()
# log = get_redis_logger(opts, "createrepo", "actions")

from .exceptions import CreateRepoError


# Some reasonable limit here for exceptional (probably buggy) situations.
# This is here mostly to not overflow the execve() stack limits.
MAX_IN_BATCH = 100


def run_cmd_unsafe(comm_str, lock_name, lock_path="/var/lock/copr-backend"):
    # log.info("Running command: {}".format(comm_str))
    comm = split(comm_str)
    title = getproctitle()
    try:
        # TODO change this to logger
        setproctitle(title + " [locked] in createrepo")
        with lockutils.lock(name=lock_name, external=True, lock_path=lock_path):
            cmd = Popen(comm, stdout=PIPE, stderr=PIPE, encoding="utf-8")
            out, err = cmd.communicate()
    except Exception as err:
        raise CreateRepoError(msg="Failed to execute: {}".format(err), cmd=comm_str)
    setproctitle(title)

    if cmd.returncode != 0:
        raise CreateRepoError(msg="exit code != 0",
                              cmd=comm_str, exit_code=cmd.returncode,
                              stdout=out, stderr=err)
    return out


def createrepo_unsafe(path, dest_dir=None, base_url=None):
    """
        Run createrepo_c on the given path

        Warning! This function doesn't check user preferences.
        In most cases use `createrepo(...)`

    :param string path: target location to create repo
    :param str dest_dir: [optional] relative to path location for repomd,
            in most cases you should also provide base_url.
    :param str base_url: optional parameter for createrepo_c, "--baseurl"

    :return tuple: (return_code,  stdout, stderr)
    """

    comm = ['/usr/bin/createrepo_c', '--database', '--ignore-lock', '--local-sqlite',
            '--cachedir', '/tmp/', '--workers', '8']
    if os.path.exists(path + '/repodata/repomd.xml'):
        comm.append("--update")
    if "epel-5" in path or "rhel-5" in path:
        # this is because rhel-5 doesn't know sha256
        comm.extend(['-s', 'sha', '--checksum', 'md5'])

    if dest_dir:
        dest_dir_path = os.path.join(path, dest_dir)
        comm.extend(['--outputdir', dest_dir_path])
        if not os.path.exists(dest_dir_path):
            os.makedirs(dest_dir_path)

    if base_url:
        comm.extend(['--baseurl', base_url])

    mb_comps_xml_path = os.path.join(path, "comps.xml")
    if os.path.exists(mb_comps_xml_path):
        comm.extend(['--groupfile', mb_comps_xml_path, '--keep-all-metadata'])

    comm.append(path)

    return run_cmd_unsafe(" ".join(map(str, comm)), os.path.join(path, "createrepo.lock"))


APPDATA_CMD_TEMPLATE = \
    """/usr/bin/timeout --kill-after=240 180 \
/usr/bin/appstream-builder \
--temp-dir={packages_dir}/tmp \
--cache-dir={packages_dir}/cache \
--packages-dir={packages_dir} \
--output-dir={packages_dir}/appdata \
--basename=appstream \
--include-failed \
--min-icon-size=48 \
--veto-ignore=missing-parents \
--enable-hidpi \
--origin={username}/{projectname}
"""
INCLUDE_APPSTREAM = \
    """/usr/bin/modifyrepo_c \
--no-compress \
{packages_dir}/appdata/appstream.xml.gz \
{packages_dir}/repodata
"""
INCLUDE_ICONS = \
    """/usr/bin/modifyrepo_c \
--no-compress \
{packages_dir}/appdata/appstream-icons.tar.gz \
{packages_dir}/repodata
"""

INCLUDE_MODULES = \
    """/usr/bin/modifyrepo_c \
--mdtype modules \
--compress-type gz \
{packages_dir}/modules.yaml \
{packages_dir}/repodata
"""

def add_appdata(path, username, projectname, lock=None):
    out = ""

    # We need to have a possibility to disable an appstream builder for some projects
    # because it doesn't properly scale up for a large ammount of packages
    parent_dir = os.path.dirname(os.path.normpath(path))

    # We don't generate appstream metadata for anything else than the main
    # directory.  If we reconsidered this in future, we would have to check the
    # file ../../<main_dir>/.disable-appstream for existance.
    if ":" in os.path.basename(parent_dir):
        return out

    if os.path.exists(os.path.join(parent_dir, ".disable-appstream")):
        return out

    kwargs = {
        "packages_dir": path,
        "username": username,
        "projectname": projectname
    }
    try:
        out += "\n" + run_cmd_unsafe(
            APPDATA_CMD_TEMPLATE.format(**kwargs), os.path.join(path, "createrepo.lock"))

        if os.path.exists(os.path.join(path, "appdata", "appstream.xml.gz")):
            out += "\n" + run_cmd_unsafe(
                INCLUDE_APPSTREAM.format(**kwargs), os.path.join(path, "createrepo.lock"))

        if os.path.exists(os.path.join(path, "appdata", "appstream-icons.tar.gz")):
            out += "\n" + run_cmd_unsafe(
                INCLUDE_ICONS.format(**kwargs), os.path.join(path, "createrepo.lock"))

        # appstream builder provide strange access rights to result dir
        # fix them, so that lighttpd could serve appdata dir
        out += "\n" + run_cmd_unsafe("chmod -R +rX {packages_dir}/appdata"
                                     .format(**kwargs), os.path.join(path, "createrepo.lock"))
    except CreateRepoError as err:
        err.stdout = out + "\nLast command\n" + err.stdout
        raise
    return out


def add_modules(path):
    if os.path.exists(os.path.join(path, "modules.yaml")):
        return run_cmd_unsafe(
            INCLUDE_MODULES.format(packages_dir=path), os.path.join(path, "createrepo.lock")
        )
    return ""


def createrepo(path, username, projectname, devel=False, base_url=None):
    """
    Creates repodata.  Depending on the "auto_createrepo" parameter it either
    creates the repodata directory in `path`, or in `path/devel`.

    :param path: directory with rpms
    :param username: copr project owner username
    :param projectname: copr project name
    :param devel: create the repository in 'devel' subdirectory
    :param base_url: base_url to access rpms independently of repomd location

    :return: tuple(returncode, stdout, stderr) produced by `createrepo_c`
    """
    # TODO: add means of logging
    if not devel:
        out_cr = createrepo_unsafe(path)
        out_ad = add_appdata(path, username, projectname)
        out_md = add_modules(path)
        return "\n".join([out_cr, out_ad, out_md])

    # Automatic createrepo disabled.  Even so, we still need to createrepo in
    # special "devel" directory so we can later build packages against it.
    return createrepo_unsafe(path, base_url=base_url, dest_dir="devel")


class BatchedCreaterepo:
    """
    Group a "group-able" set of pending createrepo tasks, and execute
    the createrepo_c binary only once for the batch.  As a result, some
    `copr-repo` processes do slightly more work (negligible difference compared
    to overall createrepo_c cost) but some do nothing.

    Note that this is wrapped into separate class mostly to make the unittesting
    easier.

    The process goes like this:

    1. BatchedCreaterepo() is instantiated by caller.
    2. Before caller acquires createrepo lock, caller notifies other processes
       by make_request().
    3. Caller acquires createrepo lock.
    4. Caller assures that no other process already did it's task, by calling
       check_processed() method (if done, caller _ends_).  Others are now
       waiting for lock so they can not process our task in the meantime.
    5. Caller get's "unified" createrepo options that are needed by the other
       queued processes by calling options() method.  These options are then
       merged with options needed by caller's task, and createrepo_c is
       executed.  Now we are saving the resources.
    6. The commit() method is called (under lock) to notify others that they
       don't have to duplicate the efforts and waste resources.
    """
    # pylint: disable=too-many-instance-attributes

    def __init__(self, dirname, full, add, delete, log,
                 devel=False,
                 appstream=True,
                 backend_opts=None,
                 noop=False):
        self.noop = noop
        self.log = log
        self.dirname = dirname
        self.devel = devel
        self.appstream = appstream


        if not backend_opts:
            self.log.error("can't get access to redis, batch disabled")
            self.noop = True
            return

        self._pid = os.getpid()
        self._json_redis_task = json.dumps({
            "appstream": appstream,
            "devel": devel,
            "add": add,
            "delete": delete,
            "full": full,
        })

        self.notify_keys = []
        self.redis = get_redis_connection(backend_opts)

    @property
    def key(self):
        """ Our instance ID (key in Redis DB) """
        return "createrepo_batched::{}::{}".format(
            self.dirname, self._pid)

    @property
    def key_pattern(self):
        """ Redis key pattern for potential tasks we can batch-process """
        return "createrepo_batched::{}::*".format(self.dirname)

    def make_request(self):
        """ Request the task into Redis DB.  Run _before_ lock! """
        if self.noop:
            return None
        self.redis.hset(self.key, "task", self._json_redis_task)
        return self.key

    def check_processed(self):
        """
        Drop our entry from Redis DB (if any), and return True if the task is
        already processed.  Requires lock!
        """
        if self.noop:
            return False

        self.log.debug("Checking if we have to start actually")
        status = self.redis.hget(self.key, "status")
        self.redis.delete(self.key)
        if status is None:
            # not yet processed
            return False

        self.log.debug("Task has already status %s", status)
        return status == "success"

    def options(self):
        """
        Get the options from other _compatible_ (see below) Redis tasks, and
        plan the list of tasks in self.notify_keys[] that we will notify in
        commit().

        We don't merge tasks that have a different 'devel' parameter.  We
        wouldn't be able to tell what sub-tasks are to be created in/out the
        devel subdirectory.

        Similarly, we don't group tasks that have different 'appstream' value.
        That's because normally (not-grouped situation) the final state of
        repository would be order dependent => e.g. if build_A requires
        appstream metadata, and build_B doesn't, the B appstream metadata would
        be added only if build_A was processed after build_B (not vice versa).
        This problem is something we don't want to solve at options() level, and
        we want rather let two concurrent processes in race (it requires at
        least one more createrepo run, but the "appstream" flag shouldn't change
        frequently anyway).
        """
        add = set()
        delete = set()
        full = False

        if self.noop:
            return (full, add, delete)

        for key in self.redis.keys(self.key_pattern):
            assert key != self.key

            task_dict = self.redis.hgetall(key)
            if task_dict.get("status") is not None:
                # skip processed tasks
                self.log.info("Key %s already processed, skip", key)
                continue

            task_opts = json.loads(task_dict["task"])

            skip = False
            for attr in ["devel", "appstream"]:
                our_value = getattr(self, attr)
                if task_opts[attr] != our_value:
                    self.log.info("'%s' attribute doesn't match: %s/%s",
                                  attr, task_opts[attr], our_value)
                    skip = True
                    break

            if skip:
                continue

            # we can process this task!
            self.notify_keys.append(key)

            # inherit "full" request from others
            if task_opts["full"]:
                full = True
                add = set()

            # append "add" tasks, if that makes sense
            if not full:
                add.update(task_opts["add"])

            # always process the delete requests
            delete.update(task_opts["delete"])

            if len(self.notify_keys) >= MAX_IN_BATCH:
                self.log.info("Batch copr-repo limit %s reached, skip the rest",
                              MAX_IN_BATCH)
                break

        return (full, add, delete)

    def commit(self):
        """
        Report that we processed other createrepo requests.  We don't report
        about failures, we rather kindly let the responsible processes to re-try
        the createrepo tasks.  Requires lock!
        """
        if self.noop:
            return

        for key in self.notify_keys:
            self.log.info("Notifying %s that we succeeded", key)
            self.redis.hset(key, "status", "success")
