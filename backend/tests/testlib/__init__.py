"""
Library for testing copr-backend
"""

import json
import os
import shutil
from unittest.mock import MagicMock

from copr_backend.background_worker_build import COMMANDS
from copr_backend.sshcmd import SSHConnection, SSHConnectionError


def minimal_be_config(where, overrides=None):
    """
    Create minimal be config which is parseable by BackendConfigReader.
    """

    destdir = os.path.join(where, "results")
    try:
        os.mkdir(destdir)
    except FileExistsError:
        pass

    setup = {
        "redis_port": "7777",
        "results_baseurl": "https://example.com/results",
        "destdir": destdir,
    }
    if overrides:
        setup.update(overrides)

    minimal_config_snippet = "[backend]\n"
    for key, value in setup.items():
        minimal_config_snippet += "{}={}\n".format(key, value)

    be_config_file = os.path.join(where, "copr-be.conf")
    with open(be_config_file, "w") as cfg_fd:
        cfg_fd.write(minimal_config_snippet)
    return be_config_file


VALID_RPM_JOB = {
    "build_id": 848963,
    "buildroot_pkgs": [],
    "chroot": "fedora-30-x86_64",
    "enable_net": False,
    "fetch_sources_only": True,
    "git_hash": "f9189466300e97944eaa9e581aec7a2c3453823d",
    "git_repo": "@copr/TEST1575431880356948981Project10/example",
    "memory_reqs": 2048,
    "package_name": "example",
    "package_version": "1.0.14-1.fc31",
    "project_dirname": "TEST1575431880356948981Project10",
    "project_name": "TEST1575431880356948981Project10",
    "project_owner": "@copr",
    "repos": [{
        "baseurl": "https://download.copr-dev.fedorainfracloud.org/"
                   "results/@copr/TEST1575431880356948981Project10/fedora-30-x86_64/",
        "id": "copr_base",
        "name": "Copr repository"
    }],
    "sandbox": "@copr/TEST1575431880356948981Project10--praiskup",
    "source_json": json.dumps({
        "clone_url": "https://copr-dist-git-dev.fedorainfracloud.org/"
                     "git/@copr/TEST1575431880356948981Project10/"
                     "example.git",
        "committish": "f9189466300e97944eaa9e581aec7a2c3453823d",
    }),
    "source_type": 8,
    "submitter": "praiskup",
    "task_id": "848963-fedora-30-x86_64",
    "timeout": 75600,
    "use_bootstrap_container": False,
    "uses_devel_repo": False,
    "with_opts": [],
    "without_opts": [],
    "appstream": True,
    "tags": ["test_tag"],
}


VALID_SRPM_JOB = {
    "build_id": 855954,
    "chroot": None,
    "project_dirname": "PROJECT_2",
    "project_name": "PROJECT_2",
    "project_owner": "@copr",
    "sandbox": "@copr/PROJECT_2--praiskup",
    "source_json": json.dumps({
        "type": "git",
        "clone_url": "https://pagure.io/copr/copr-hello.git",
        "committish": "",
        "subdirectory": "",
        "spec": "",
        "srpm_build_method": "rpkg",
    }),
    "source_type": 8,
    "submitter": "praiskup",
    "task_id": "855954",
    "appstream": True,
}


class TimeSequenceSideEffect:
    """
    Mimic time.time(), and at special time call special function
    """
    def __init__(self, sequence, special_cases):
        self.sequence = sequence
        self.special_cases = special_cases
        self.counter = 0

    def __call__(self):
        retval = self.sequence[self.counter]
        self.counter += 1
        if retval in self.special_cases:
            self.special_cases[retval]()
        return retval


class FakeSSHConnection(SSHConnection):
    """ replacement for SSHConnection """
    unlink_success = False
    precreate_compressed_log_file = False

    def __init__(self, user=None, host=None, config_file=None, log=None):
        _unused = user, host, config_file
        super().__init__(log=log)
        self.commands = {}
        self.set_command(COMMANDS["rpm_q_builder"],
                         0, "666\n", "")
        self.set_command("/usr/bin/test -f /etc/mock/fedora-30-x86_64.cfg",
                         0, "", "")
        self.set_command("copr-rpmbuild-log",
                         0, "build log stdout\n", "build log stderr\n")

    def set_command(self, cmd, exit_code, stdout, stderr, action=None,
                    return_action=None):
        """ setup expected output """
        self.commands[cmd] = (exit_code, stdout, stderr, action, return_action)

    def get_command(self, cmd):
        """ get predefined command output, and call the action """
        try:
            res = self.commands[cmd]
            if res[3]:
                res[3]()
            if res[4]:
                return res[4]()
            return res
        except KeyError:
            raise SSHConnectionError("undefined cmd '{}' in FakeSSHConnection"
                                     .format(cmd))

    def run(self, user_command, stdout=None, stderr=None, max_retries=0):
        """ fake SSHConnection.run() """
        with open(os.devnull, "w") as devnull:
            out = stdout or devnull
            err = stderr or devnull
            res = self.get_command(user_command)
            out.write(res[1])
            err.write(res[2])
            return res[0]

    def run_expensive(self, user_command, max_retries=0):
        """ fake SSHConnection.run_expensive() """
        res = self.get_command(user_command)
        return (res[0], res[1], res[2])

    def _ssh_base(self):
        return ["ssh"]

    def _full_source_path(self, src):
        return src

    def rsync_download(self, src, dest, logfile=None, max_retries=0):
        data = os.environ["TEST_DATA_DIRECTORY"]
        trail_slash = src.endswith("/")
        src = os.path.join(data, "build_results", "00848963-example")
        if trail_slash:
            src = src + "/"

        self.log.info("rsync from src=%s to dest=%s", src, dest)

        super().rsync_download(src, dest, logfile)
        os.unlink(os.path.join(dest, "backend.log.gz"))

        if not self.precreate_compressed_log_file:
            os.unlink(os.path.join(dest, "builder-live.log.gz"))

        if self.unlink_success:
            os.unlink(os.path.join(dest, "success"))

        if "PROJECT_2" in dest:
            os.unlink(os.path.join(dest, "example-1.0.14-1.fc30.x86_64.rpm"))

def assert_logs_exist(messages, caplog):
    """
    Search through caplog entries for log records having all the messages in
    ``messages`` list.
    """
    search_for = set(messages)
    found = set()
    for record in caplog.record_tuples:
        _, _, msg = record
        for search in search_for:
            if search in msg:
                found.add(search)
    assert found == search_for

def assert_logs_dont_exist(messages, caplog):
    """
    Search through caplog entries for log records having all the messages in
    ``messages`` list.
    """
    search_for = set(messages)
    found = set()
    for record in caplog.record_tuples:
        _, _, msg = record
        for search in search_for:
            if search in msg:
                found.add(search)
    assert found == set({})

def assert_files_in_dir(directory, exist, dont_exist):
    """
    Check for (non-)existence of files in directory
    """
    for subdir in exist + dont_exist:
        filename = os.path.join(directory, subdir)
        expected_to_exist = subdir in exist
        assert expected_to_exist == os.path.exists(filename)

class AsyncCreaterepoRequestFactory:
    """ Generator for asynchronous craeterepo requests """
    def __init__(self, redis):
        self.pid = os.getpid()
        self.redis = redis

    def get(self, dirname, overrides=None, done=False):
        """ put new request to redis """
        task = {
            "appstream": True,
            "devel": False,
            "add": ["add_1"],
            "delete": [],
            "full": False,
            "rpms_to_remove": [],
        }
        self.pid += 1
        if overrides:
            task.update(overrides)
        key = "createrepo_batched::{}::{}".format(dirname, self.pid)
        task_json = json.dumps(task)
        self.redis.hset(key, "task", task_json)
        if done:
            self.redis.hset(key, "status", "success")
