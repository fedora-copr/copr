# coding: utf-8

"""
Test the BuildBackgroundWorker from background_worker_build.py
"""

import copy
import logging
import glob
import json
import os
import shutil
import subprocess
import time
import tempfile
from unittest import mock

from munch import Munch
import pytest

from copr_backend.constants import LOG_REDIS_FIFO
from copr_backend.background_worker_build import (
    BuildBackgroundWorker, MESSAGES, BackendError, _average_step,
)
from copr_backend.job import BuildJob
from copr_backend.exceptions import CoprSignError
from copr_backend.vm_alloc import ResallocHost, RemoteHostAllocationTerminated
from copr_backend.background_worker_build import COMMANDS, MIN_BUILDER_VERSION
from copr_backend.sshcmd import SSHConnectionError
from copr_backend.exceptions import CoprBackendSrpmError

import testlib
from testlib import assert_logs_exist, assert_logs_dont_exist
from testlib.repodata import load_primary_xml

# pylint: disable=redefined-outer-name,protected-access

COMMON_MSGS = {
    "not finished": "Switching not-finished job state to 'failed'",
}

def _patch_bw_object(obj, *args, **kwargs):
    return mock.patch("copr_backend.background_worker.{}".format(obj),
                      *args, **kwargs)

def _patch_bwbuild_object(obj, *args, **kwargs):
    return mock.patch("copr_backend.background_worker_build.{}".format(obj),
                      *args, **kwargs)

def _get_rpm_job_object_dict(updated=None):
    job = copy.deepcopy(testlib.VALID_RPM_JOB)
    if updated:
        job.update(updated)
    return job

def _get_rpm_job_object(opts, updated=None):
    job = _get_rpm_job_object_dict(updated)
    return BuildJob(job, opts)

def _get_rpm_job(updated=None):
    job = _get_rpm_job_object_dict(updated)
    response = Munch()
    response.status_code = 200
    response.json = lambda: job
    return response

def _get_srpm_job(updated=None):
    job = copy.deepcopy(testlib.VALID_SRPM_JOB)
    if updated:
        job.update(updated)
    response = Munch()
    response.status_code = 200
    response.json = lambda: job
    return response

def _reset_build_worker():
    worker = BuildBackgroundWorker()
    # Don't waste time with mocking.  We don't want to log anywhere, and we want
    # to let BuildBackgroundWorker adjust the handlers.
    worker.log.handlers = []
    return worker

def _fake_host():
    host = ResallocHost()
    host._is_ready = True
    host.hostname = "1.2.3.4"
    host.ticket = mock.MagicMock()
    host.ticket.id = 10
    host.release = mock.MagicMock()
    return host

@pytest.fixture
def f_build_something():
    """
    Prepare worker for RPM or SRPM build
    """
    config = Munch()
    config.workdir = tempfile.mkdtemp(prefix="build-worker-tests-")
    config.be_config_file = testlib.minimal_be_config(config.workdir)

    patchers = [_patch_bw_object("FrontendClient")]
    config.fe_client = patchers[-1].start()

    patchers += [_patch_bwbuild_object("MessageSender")]
    patchers[-1].start()

    config.fe_client_patcher = _patch_bw_object("FrontendClient")
    config.fe_client = config.fe_client_patcher.start()

    config.worker_id = "fake_worker_id_" + str(time.time())

    patchers.append(
        mock.patch("copr_backend.background_worker.sys.argv",
                   ["test-build", "--build-id", "848963",
                    "--worker-id", config.worker_id, "--silent",
                    "--backend-config", config.be_config_file,
                    "--chroot", "fedora-30-x86_64"]),
    )
    patchers[-1].start()

    patchers.append(mock.patch.dict(os.environ, {
        "COPR_BE_CONFIG": config.be_config_file,
        "COPR_TESTSUITE_LOCKPATH": config.workdir,
    }))
    patchers[-1].start()

    config.bw = _reset_build_worker()
    config.bw.redis_set_worker_flag("allocated", "true")

    # Don't waste time with mocking.  We don't want to log anywhere, and we want
    # to let BuildBackgroundWorker adjust the handlers.
    config.bw.log.handlers = []

    patcher = _patch_bwbuild_object("ResallocHostFactory")
    patchers.append(patcher)
    rhf = patcher.start()
    config.host = host = _fake_host()
    rhf.return_value.get_host.return_value = host
    config.resalloc_host_factory = rhf

    config.ssh = testlib.FakeSSHConnection(user="remoteuser", host=host.hostname)
    ssh_patcher = _patch_bwbuild_object("SSHConnection")
    ssh_class = ssh_patcher.start()
    ssh_class.return_value = config.ssh
    patchers.append(ssh_patcher)

    yield config
    for patcher in patchers:
        patcher.stop()
    shutil.rmtree(config.workdir)

    # Clear the adjusted handlers.
    config.bw.log.handlers = []

@pytest.fixture
def f_build_rpm_case_no_repodata(f_build_something):
    """
    Configure the situation when 'copr-backend-process-build' is requested
    to build RPM.
    """
    config = f_build_something
    config.fe_client.return_value.get.return_value = _get_rpm_job()
    yield config

@pytest.fixture
def f_build_srpm(f_build_something):
    """
    Configure the situation when 'copr-backend-process-build' is requested
    to build RPM.
    """
    config = f_build_something
    config.fe_client.return_value.get.return_value = _get_srpm_job()
    config.ssh.set_command(
        "copr-rpmbuild --verbose --drop-resultdir --srpm --build-id 855954 "
        "--detached",
        0, "666", "",
    )

    patcher = mock.patch(
        "copr_backend.background_worker.sys.argv",
        ["test-build", "--build-id", "848963",
         "--worker-id", config.worker_id, "--silent",
         "--backend-config", config.be_config_file,
         "--chroot", "srpm-builds"],
    )
    patcher.start()
    config.bw = _reset_build_worker()
    yield config
    patcher.stop()

def _create_repodata(in_dir):
    repodata = os.path.join(in_dir, "repodata")
    os.makedirs(repodata)
    repomd = os.path.join(repodata, "repomd.xml")
    with open(repomd, "w"):
        pass


def _create_job_repodata(job):
    _create_repodata(job.chroot_dir)


@pytest.fixture
def f_build_rpm_case(f_build_rpm_case_no_repodata):
    """
    Prepare everything, so the build can succeed.
    """
    config = f_build_rpm_case_no_repodata
    chroot = os.path.join(f_build_rpm_case_no_repodata.workdir, "results",
                          "@copr",
                          "TEST1575431880356948981Project10",
                          "fedora-30-x86_64")
    _create_repodata(chroot)

    config.ssh.set_command(
        "copr-rpmbuild --verbose --drop-resultdir --build-id 848963 "
        "--chroot fedora-30-x86_64 --detached",
        0, "666", "",
    )
    yield f_build_rpm_case_no_repodata

@pytest.fixture
def f_build_rpm_sign_on(f_build_rpm_case):
    """
    f_build_rpm_case with enabled GPG signing ON
    """
    config = f_build_rpm_case
    with open(config.be_config_file, "a+") as fdconfig:
        fdconfig.write("do_sign=true\n")
        fdconfig.write("keygen_host=keygen.example.com\n")
        fdconfig.write("gently_gpg_sha256=false\n")
    config.bw = _reset_build_worker()
    return config

@_patch_bwbuild_object("time")
def test_waiting_for_repo_fail(mc_time, f_build_rpm_case_no_repodata, caplog):
    """ check that worker loops in _wait_for_repo """
    worker = f_build_rpm_case_no_repodata.bw
    mc_time.time.side_effect = [1, 2, 3, 4, 5, 6, 120, 121]
    worker.process()
    expected = [
        (logging.ERROR, str(BackendError(MESSAGES["give_up_repo"]))),
        (logging.INFO, MESSAGES["repo_waiting"]),
    ]
    for exp in expected:
        assert exp in [(r[1], r[2]) for r in caplog.record_tuples]

@_patch_bwbuild_object("time")
def test_waiting_for_repo_success(mc_time, f_build_rpm_case_no_repodata, caplog):
    """ check that worker loops in _wait_for_repo """
    worker = f_build_rpm_case_no_repodata.bw

    # on the 6th call to time(), create the repodata
    mc_time.time.side_effect = testlib.TimeSequenceSideEffect(
        [1, 2, 3, 4, 5, 6, 120],
        {6: lambda: _create_job_repodata(worker.job)}
    )

    # shutdown ASAP after _wait_for_repo() call
    def raise_exc():
        raise Exception("duh")
    worker._alloc_host = mock.MagicMock()
    worker._alloc_host.side_effect = raise_exc
    worker.process()

    # _wait_for_repo() succeeded, and we continued to _alloc_host()
    assert len(worker._alloc_host.call_args_list) == 1

    assert (logging.INFO, MESSAGES["repo_waiting"]) \
        in [(r[1], r[2]) for r in caplog.record_tuples]

@_patch_bwbuild_object("BuildBackgroundWorker._parse_results")
def test_full_rpm_build_no_sign(_parse_results, f_build_rpm_case, caplog):
    """
    Go through the whole (successful) build of a binary RPM
    """
    worker = f_build_rpm_case.bw
    worker.process()

    results = worker.job.results_dir
    assert os.path.exists(os.path.join(results, "builder-live.log.gz"))
    assert os.path.exists(os.path.join(results, "backend.log.gz"))

    found_success_log_entry = False
    for record in caplog.record_tuples:
        _, level, msg = record
        assert level < logging.ERROR
        if "Finished build: id=848963 failed=False" in msg:
            found_success_log_entry = True
    assert found_success_log_entry

    repodata = load_primary_xml(os.path.join(results, "..", "repodata"))
    assert repodata["names"] == {"example"}
    assert repodata["packages"]["example"]["href"] == \
        "00848963-example/example-1.0.14-1.fc30.x86_64.rpm"

    assert worker.job.built_packages == "example 1.0.14"
    assert_messages_sent(["build.start", "chroot.start", "build.end"], worker.sender)

def test_prev_build_backup(f_build_rpm_case):
    worker = f_build_rpm_case.bw
    worker.process()
    worker.process()
    prev_results = os.path.join(worker.job.results_dir, "prev_build_backup")
    assert glob.glob(os.path.join(prev_results, '*.rpm')) == []
    assert os.path.exists(os.path.join(prev_results, "builder-live.log.gz"))
    assert os.path.exists(os.path.join(prev_results, "backend.log.gz"))
    rsync_patt = "*{}.rsync.log".format(worker.job.build_id)
    assert len(glob.glob(os.path.join(prev_results, rsync_patt))) == 1

def test_full_srpm_build(f_build_srpm):
    worker = f_build_srpm.bw
    worker.process()
    assert worker.job.pkg_name == "example"

    # TODO: fix this is ugly pkg_version testament
    assert worker.job.pkg_version is None
    assert worker.job.__dict__["pkg_version"] == "1.0.14-1.fc30"

    assert worker.job.srpm_url == (
        "https://example.com/results/@copr/PROJECT_2/srpm-builds/"
        "00855954/example-1.0.14-1.fc30.src.rpm")

@mock.patch("copr_backend.sign.SIGN_BINARY", "tests/fake-bin-sign")
@mock.patch("copr_backend.sign._sign_one")
@_patch_bwbuild_object("BuildBackgroundWorker._parse_results")
def test_build_and_sign(_parse_results, mc_sign_one, f_build_rpm_sign_on, caplog):
    config = f_build_rpm_sign_on
    worker = config.bw
    worker.process()
    pub_key = os.path.join(worker.job.destdir, "pubkey.gpg")
    with open(pub_key, "r") as pub:
        content = pub.readlines()
        assert content == ["fake pub key content\n"]

    mail = "@copr#TEST1575431880356948981Project10@copr.fedorahosted.org"
    rpm = os.path.join(worker.job.results_dir,
                       "example-1.0.14-1.fc30.x86_64.rpm")
    srpm = os.path.join(worker.job.results_dir,
                        "example-1.0.14-1.fc30.src.rpm")
    expected_calls = [
        mock.call(rpm, mail, "sha256", mc_sign_one.call_args_list[0][0][3]),
        mock.call(srpm, mail, "sha256", mc_sign_one.call_args_list[1][0][3]),
    ]
    for call in expected_calls:
        assert call in mc_sign_one.call_args_list
    assert len(mc_sign_one.call_args_list) == 2
    for record in caplog.record_tuples:
        _, level, _ = record
        assert level <= logging.INFO

@mock.patch("copr_backend.sign.SIGN_BINARY", "tests/fake-bin-sign")
@mock.patch("copr_backend.sign._sign_one")
@_patch_bwbuild_object("sign_rpms_in_dir")
def test_sign_built_packages_exception(mc_sign_rpms, mc_sign_one,
                                       f_build_rpm_sign_on, caplog):
    _side_effect = mc_sign_one
    mc_sign_rpms.side_effect = CoprSignError("test")
    config = f_build_rpm_sign_on
    worker = config.bw
    worker.process()
    messages = [
        (logging.ERROR, "Copr GPG signing problems: test"),
    ]
    found_fail = False
    for msg in messages:
        assert msg in [(r[1], r[2]) for r in caplog.record_tuples]
    for msg in caplog.record_tuples:
        _, _, text = msg
        if "Finished build: id=848963 failed=True" in text:
            found_fail = True
    assert found_fail

def _get_log_content(job, log="backend.log.gz"):
    logfile = os.path.join(job.results_dir, log)
    cmd = ["gunzip", "-c", logfile]
    return subprocess.check_output(cmd).decode("utf-8")

def test_unexpected_exception(f_build_rpm_case, caplog):
    config = f_build_rpm_case
    worker = config.bw
    def _raise():
        raise IOError("blah")

    worker._check_vm = _raise
    worker.process()

    redis = worker._redis
    log_entry = None

    # check that the traceback is logged to worker.log
    while True:
        log_entry = redis.rpop(LOG_REDIS_FIFO)
        if not log_entry:
            break
        if "Traceback" in log_entry:
            break

    log_dict = json.loads(log_entry)
    msg = "Unexpected exception\nTraceback (most recent call last)"
    assert msg in log_dict["msg"]

    content = _get_log_content(worker.job)
    assert "Traceback" not in content

    found_line = None
    for line in content.splitlines():
        if "Unexpected exception" in line:
            found_line = line
            break

    # check that the shortened variant is in log
    assert "/test_background_worker_build.py:" in found_line

def test_build_info_file_failure(f_build_rpm_case):
    config = f_build_rpm_case
    worker = config.bw
    worker.job = _get_rpm_job_object(worker.opts)
    os.makedirs(worker.job.results_dir)
    info_file = os.path.join(worker.job.results_dir, "build.info")
    worker.host = Munch()
    worker.host.hostname = "0.0.0.0"
    worker._fill_build_info_file()
    with open(info_file, "r") as info_fd:
        content = info_fd.readlines()
        # TODO: fix missing newline
        assert content == ['build_id=848963\n', 'builder_ip=0.0.0.0']
    # make it "non-writable"
    os.unlink(info_file)
    os.mkdir(info_file)
    with pytest.raises(BackendError) as err:
        worker._fill_build_info_file()
    assert "Backend process error: Can't write to " in str(err.value)
    assert "00848963-example/build.info'" in str(err.value)

def test_invalid_job_info(f_build_rpm_case, caplog):
    config = f_build_rpm_case
    worker = config.bw
    get = config.fe_client.return_value.get.return_value
    job = get.json()
    del job["chroot"]
    worker.process()
    assert_logs_exist([
        "Backend process error: Frontend job doesn't provide chroot",
        COMMON_MSGS["not finished"],
    ], caplog)
    assert_logs_dont_exist([
        "took None",
    ], caplog)

@mock.patch("copr_backend.vm_alloc.time.sleep", mock.MagicMock())
@_patch_bwbuild_object("CANCEL_CHECK_PERIOD", 0.5)
@mock.patch("copr_backend.sign.SIGN_BINARY", "tests/fake-bin-sign")
def test_cancel_build_on_vm_allocation(f_build_rpm_sign_on, caplog):
    config = f_build_rpm_sign_on
    worker = config.bw

    # let it think it is started by "worker manager"
    class _CheckReady:
        attempt = 0
        def __call__(self):
            # process() configures logging, so drop the loggers to avoid
            # an ugly test output
            self.attempt += 1
            if self.attempt > 3:
                # Deliver cancel request to checker thread (this is
                # delivered by WorkerManager normally).
                worker.redis_set_worker_flag("cancel_request", 1)

            # When the "cancel_request" is processed, we get the "canceling"
            # response.  Resalloc client would normally recognize that the
            # ticket is closed, and raised RemoteHostAllocationTerminated.
            if worker.redis_get_worker_flag("canceling"):
                raise RemoteHostAllocationTerminated
            return False

    config.host._is_ready = False
    config.host.check_ready = mock.MagicMock()
    config.host.check_ready.side_effect = _CheckReady()

    found_records = {}
    def _find_records(record_msg):
        msgs = [
            "Build was canceled", # cancel handled
            COMMON_MSGS["not finished"],
            "Worker failed build", # needs to finish
            "Unable to compress file", # there's no builder-live.log yet
        ]
        for msg in msgs:
            if not msg in found_records:
                found_records[msg] = False
            if msg in record_msg:
                found_records[msg] = True

    worker.process()
    for record in caplog.record_tuples:
        _, _, msg = record
        _find_records(msg)
    for key, value in found_records.items():
        assert (key, value) == (key, True)
    assert worker.job.status == 0  # failure

class _CancelFunction():
    def __init__(self, worker):
        self.worker = worker
    def __call__(self):
        # request cancelation
        self.worker.redis_set_worker_flag("cancel_request", 1)
        # and do something till _cancel_vm_allocation() doesn't let us know
        while self.worker.redis_get_worker_flag("canceling") is None:
            time.sleep(0.25)

@_patch_bwbuild_object("CANCEL_CHECK_PERIOD", 0.5)
@mock.patch("copr_backend.sign.SIGN_BINARY", "tests/fake-bin-sign")
def test_cancel_build_on_tail_log_no_ssh(f_build_rpm_sign_on, caplog):
    config = f_build_rpm_sign_on
    worker = config.bw

    config.ssh.set_command(
        "copr-rpmbuild-log",
        0, "canceled stdout\n", "canceled stderr\n",
        _CancelFunction(worker),
    )
    worker.process()
    exp_msgs = {
        "Can't ssh to cancel build.",
        "Build was canceled",
        COMMON_MSGS["not finished"],
        "Worker failed build",
    }
    found_messages = set()

    for record in caplog.record_tuples:
        _, _, msg = record
        for exp_msg in exp_msgs:
            if exp_msg in msg:
                found_messages.add(exp_msg)
    assert exp_msgs == found_messages
    log = _get_log_content(worker.job, "builder-live.log.gz")
    assert "canceled stdout" in log

@_patch_bwbuild_object("CANCEL_CHECK_PERIOD", 0.5)
@mock.patch("copr_backend.sign.SIGN_BINARY", "tests/fake-bin-sign")
def test_cancel_before_vm(f_build_rpm_sign_on, caplog):
    config = f_build_rpm_sign_on
    worker = config.bw
    # set this early
    worker.redis_set_worker_flag("cancel_request", 1)
    worker.process()
    assert_logs_exist([
        "Build was canceled",
        "Canceling the build early",
        COMMON_MSGS["not finished"],
        "Worker failed build",
    ], caplog)
    assert_logs_dont_exist(["Releasing VM back to pool"], caplog)

@_patch_bwbuild_object("CANCEL_CHECK_PERIOD", 0.5)
@mock.patch("copr_backend.sign.SIGN_BINARY", "tests/fake-bin-sign")
def test_cancel_before_start(f_build_rpm_sign_on, caplog):
    config = f_build_rpm_sign_on
    worker = config.bw

    # cancel request right before starting the build
    worker._fill_build_info_file = mock.MagicMock()
    worker._fill_build_info_file.side_effect = \
        lambda: worker.redis_set_worker_flag("cancel_request", 1)

    worker.process()
    assert_logs_exist([
        "Build was canceled",
        "Releasing VM back to pool",
        "Canceling the build early",
        COMMON_MSGS["not finished"],
        "Worker failed build",
    ], caplog)

@_patch_bwbuild_object("CANCEL_CHECK_PERIOD", 0.5)
@_patch_bwbuild_object("BuildBackgroundWorker._parse_results")
@mock.patch("copr_backend.sign.SIGN_BINARY", "tests/fake-bin-sign")
def test_build_retry(_parse_results, f_build_rpm_sign_on):
    config = f_build_rpm_sign_on
    worker = config.bw
    class _SideEffect():
        counter = 0
        def __call__(self):
            self.counter += 1
            if self.counter < 2:
                return (1, "out", "err")
            if self.counter < 3:
                return (0, "0.38", "")
            return (0, MIN_BUILDER_VERSION, "")

    config.ssh.set_command(
        COMMANDS["rpm_q_builder"],
        1, "err stdout\n", "err stderr\n",
        return_action=_SideEffect())

    worker.process()
    log = _get_log_content(worker.job)
    find_msgs = {
        MESSAGES["copr_rpmbuild_missing"].format("err"),
        "Minimum version for builder is " + MIN_BUILDER_VERSION,
        "Allocating ssh connection to builder",
        "Finished build: id=848963 failed=False",
    }
    found_msgs = set()
    for line in log.splitlines():
        for find in find_msgs:
            if find in line:
                found_msgs.add(find)
    assert find_msgs == found_msgs
    assert _get_log_content(worker.job, "builder-live.log.gz").splitlines() == \
        ["build log stdout", "build log stderr"]

def assert_messages_sent(topics, sender):
    """ check msg bus calls """
    assert len(topics) == len(sender.announce.call_args_list)
    for topic in topics:
        found = False
        for call in sender.announce.call_args_list:
            if topic == call[0][0]:
                found = True
        assert (found, topic) == (True, topic)

def test_fe_disallowed_start(f_build_rpm_sign_on, caplog):
    config = f_build_rpm_sign_on
    worker = config.bw
    config.fe_client.return_value.starting_build.return_value = False
    worker.process()
    assert any(["Frontend forbade to start" in r[2] for r in caplog.record_tuples])
    assert any(["Worker failed build" in r[2] for r in caplog.record_tuples])

def test_fe_failed_start(f_build_rpm_sign_on, caplog):
    config = f_build_rpm_sign_on
    worker = config.bw
    job = _get_rpm_job()
    job.status_code = 403
    config.fe_client.return_value.get.return_value = job
    worker.process()
    assert_logs_exist([
        "Failed to download build info, apache code 403",
        "Backend process error: Failed to get the build task"
        " get-build-task/848963-fedora-30-x86_64",
        "No job object from Frontend",
    ], caplog)
    # check that worker manager is notified
    assert worker.redis_get_worker_flag("status") == "done"

@_patch_bwbuild_object("CANCEL_CHECK_PERIOD", 0.5)
@mock.patch("copr_backend.sign.SIGN_BINARY", "tests/fake-bin-sign")
def test_cancel_script_failure(f_build_rpm_sign_on, caplog):
    config = f_build_rpm_sign_on
    worker = config.bw
    config.ssh.set_command(
        "copr-rpmbuild-log",
        0, "canceled stdout\n", "canceled stderr\n",
        _CancelFunction(worker),
    )
    config.ssh.set_command(
        "copr-rpmbuild-cancel",
        1, "output", "err output",
    )
    worker.process()
    assert_logs_exist([
        "Can't cancel build\nout:\noutput\nerr:\nerr output",
        "Build was canceled",
        COMMON_MSGS["not finished"],
        "Worker failed build, took",
    ], caplog)

@_patch_bwbuild_object("CANCEL_CHECK_PERIOD", 0.5)
@mock.patch("copr_backend.sign.SIGN_BINARY", "tests/fake-bin-sign")
def test_cancel_build_during_log_download(f_build_rpm_sign_on, caplog):
    config = f_build_rpm_sign_on
    worker = config.bw
    config.ssh.set_command(
        "copr-rpmbuild-log",
        0, "canceled stdout\n", "canceled stderr\n",
        _CancelFunction(worker),
    )
    config.ssh.set_command("copr-rpmbuild-cancel", 0, "out", "err")
    worker.process()
    assert_logs_exist([
        "Cancel request succeeded\nout:\nouterr:\nerr",
        "Build was canceled",
        COMMON_MSGS["not finished"],
    ], caplog)

@_patch_bwbuild_object("BuildBackgroundWorker._parse_results")
def test_ssh_connection_error(_parse_results, f_build_rpm_case, caplog):
    class _SideEffect:
        counter = 0
        def __call__(self):
            self.counter += 1
            if self.counter == 1:
                return (1, "err stdout", "err stderr")
            return (0, "", "")

    config = f_build_rpm_case
    ssh = config.ssh
    ssh.set_command("/usr/bin/test -f /etc/mock/fedora-30-x86_64.cfg",
                    0, "", "", return_action=_SideEffect())
    worker = config.bw
    worker.process()
    assert_logs_exist([
        "Retry #1 (on other host)",
        "Worker succeeded build",
    ], caplog)

def test_average_step():
    assert _average_step([]) == float("inf")
    assert _average_step([1, 2, 3]) == float("inf")
    assert _average_step([1, 2, 3, 4, 6]) == 1.25

@_patch_bwbuild_object("time.sleep", mock.MagicMock())
@_patch_bwbuild_object("time.time")
@_patch_bwbuild_object("BuildBackgroundWorker._parse_results")
def test_retry_for_ssh_tail_failure(_parse_results, mc_time, f_build_rpm_case,
                                    caplog):
    mc_time.side_effect = list(range(500))
    class _SideEffect:
        counter = 0
        def __call__(self):
            self.counter += 1
            if self.counter > 5:
                return (0, "", "")
            raise SSHConnectionError("test failure")
    config = f_build_rpm_case
    ssh = config.ssh
    ssh.set_command("copr-rpmbuild-log",
                    0, "", "", return_action=_SideEffect())
    worker = config.bw
    worker.process()
    assert_logs_exist([
        "Retry #1 (on other host)",
        "Worker succeeded build",
        "Giving up for unstable SSH",
    ], caplog)
    assert_messages_sent(["build.start", "chroot.start", "build.end"], worker.sender)

def test_build_failure(f_build_rpm_case, caplog):
    config = f_build_rpm_case
    config.ssh.unlink_success = True
    worker = config.bw
    worker.process()
    assert_logs_exist([
        "Backend process error: No success file => build failure",
        "Worker failed build, took ",
        "Finished build: id=848963 failed=True ",
    ], caplog)
    assert_messages_sent(["build.start", "chroot.start", "build.end"], worker.sender)

@_patch_bwbuild_object("call_copr_repo")
def test_createrepo_failure(mc_call_copr_repo, f_build_rpm_case, caplog):
    mc_call_copr_repo.return_value = False
    config = f_build_rpm_case
    worker = config.bw
    worker.process()
    assert_logs_exist([
        "Backend process error: createrepo failed",
        "Worker failed build, took ",
        "Finished build: id=848963 failed=True ",
    ], caplog)

@_patch_bwbuild_object("pkg_name_evr")
def test_pkg_collect_failure(mc_pkg_evr, f_build_srpm, caplog):
    mc_pkg_evr.side_effect = CoprBackendSrpmError("srpm error")
    config = f_build_srpm
    worker = config.bw
    worker.process()
    assert_logs_exist([
        "Error while collecting built packages",
        "Worker failed build, took ",
        "Finished build: id=855954 failed=True ",
    ], caplog)
    assert worker.job.status == 0  # fail

@_patch_bwbuild_object("BuildBackgroundWorker._parse_results")
def test_existing_compressed_file(_parse_results, f_build_rpm_case, caplog):
    config = f_build_rpm_case
    config.ssh.precreate_compressed_log_file = True
    worker = config.bw
    worker.process()
    assert_logs_exist([
        "Worker succeeded build, took ",
        "builder-live.log.gz exists",
        "Finished build: id=848963 failed=False ",  # still success!
    ], caplog)

@_patch_bwbuild_object("BuildBackgroundWorker._parse_results")
def test_tail_f_nonzero_exit(_parse_results, f_build_rpm_case, caplog):
    config = f_build_rpm_case
    worker = config.bw
    class _SideEffect:
        counter = 0
        def __call__(self):
            self.counter += 1
            if self.counter > 3:
                return (0, "ok\n", "ok\n")
            return (1, "fail out\n", "fail err\n")
    config.ssh.set_command(
        "copr-rpmbuild-log",
        0, "failed stdout\n", "failed stderr\n",
        return_action=_SideEffect(),
    )
    worker.process()
    assert_logs_exist([
        "Retry #3 (on other host)",
        "Worker succeeded build, took ",
        "Finished build: id=848963 failed=False ",  # still success!
    ], caplog)

def test_wrong_copr_rpmbuild_daemon_output(f_build_srpm, caplog):
    config = f_build_srpm
    config.ssh.set_command(
        "copr-rpmbuild --verbose --drop-resultdir --srpm --build-id 855954 "
        "--detached",
        0, "6a66", "",
    )
    config.bw.process()
    assert_logs_exist([
        "Backend process error: copr-rpmbuild returned invalid"
        " PID on stdout: 6a66",
        "Worker failed build, took ",
        "builder-live.log: No such file or directory",
    ], caplog)
    assert_logs_dont_exist([
        "Retry",
        "Finished build",
    ], caplog)

def test_unable_to_start_builder(f_build_srpm, caplog):
    config = f_build_srpm
    config.ssh.set_command(
        "copr-rpmbuild --verbose --drop-resultdir --srpm --build-id 855954 "
        "--detached",
        10, "stdout\n", "stderr\n",
    )
    config.bw.process()
    assert_logs_exist([
        "Can't start copr-rpmbuild",
        "out:\nstdout\nerr:\nstderr\n",
        "builder-live.log: No such file or directory",
    ], caplog)
    assert_logs_dont_exist(["Retry"], caplog)

@_patch_bwbuild_object("time.sleep", mock.MagicMock())
def test_retry_vm_factory_take(f_build_srpm, caplog):
    config = f_build_srpm
    rhf = config.resalloc_host_factory
    host = config.host
    fake_host = Munch()
    fake_host.wait_ready = lambda: False
    fake_host.release = lambda: None
    fake_host.info = "fake host"
    rhf.return_value.get_host.side_effect = [fake_host, host]
    config.bw.process()
    assert_logs_exist([
        "VM allocation failed, trying to allocate new VM",
        "Finished build: id=855954 failed=False",
    ], caplog)
    assert config.bw.job.status == 1  # success

def test_failed_build_retry(f_build_rpm_case, caplog):
    config = f_build_rpm_case
    rhf = config.resalloc_host_factory
    hosts = [_fake_host() for _ in range(4)]
    for index in range(4):
        hosts[index].hostname = "1.2.3." + str(index)
    rhf.return_value.get_host.side_effect = hosts
    ssh = config.ssh
    ssh.set_command("/usr/bin/test -f /etc/mock/fedora-30-x86_64.cfg",
                    1, "", "not found")

    config.bw.process()
    assert_logs_exist([
        "Three host tried without success: {'1.2.3.",
        COMMON_MSGS["not finished"],
        "Worker failed build, took ",
    ], caplog)
    assert config.bw.job.status == 0
    # Only build.end sent by this worker (after reset)
    assert_messages_sent(["build.end"], config.bw.sender)

def test_buildjob_tags(f_build_rpm_case):
    config = f_build_rpm_case
    worker = config.bw
    worker.job = _get_rpm_job_object(worker.opts)
    assert worker.job.tags == ['arch_x86_64', 'test_tag']
