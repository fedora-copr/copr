# coding: utf-8

import logging
from munch import Munch
import time

import tempfile
import shutil
import os
import pytest

from unittest import mock
from unittest.mock import patch, MagicMock

from copr_backend.daemons.log import RedisLogHandler


@pytest.yield_fixture
def mc_logging():
    with mock.patch("copr_backend.daemons.log.logging") as mc_logging:
        yield mc_logging


@pytest.yield_fixture
def mc_setproctitle():
    with mock.patch("copr_backend.daemons.log.setproctitle") as mc_spt:
        yield mc_spt


class TestLog(object):

    def setup_method(self, method):

        self.mc_mpp_patcher = mock.patch("copr_backend.daemons.log.Process")
        self.mc_mpp = self.mc_mpp_patcher.start()

        self.test_time = time.time()
        subdir = "test_createrepo_{}".format(time.time())
        # self.tmp_dir_path = os.path.join(tempfile.gettempdir(), subdir)
        self.tmp_dir_path = "/tmp/redis_log"
        if not os.path.exists(self.tmp_dir_path):
            os.mkdir(self.tmp_dir_path)

        self.log_dir = os.path.join(self.tmp_dir_path, "copr")
        self.log_file = os.path.join(self.log_dir, "copr.log")
        self.opts = Munch(
            verbose=False,
            log_dir=self.log_dir
        )
        print("\n log dir: {}".format(self.log_dir))
        self.queue = MagicMock()

    def teardown_method(self, method):
        self.mc_mpp_patcher.stop()

        # shutil.rmtree(self.tmp_dir_path)
        if hasattr(self, "cbl"):
            del self.cbl

        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

    @pytest.fixture
    def init_log(self):
        pass

    # todo: replace with RedisLogHandler + helpers.get_redis_logger
    # def test_constructor(self):
    #     # with mock.patch("copr_backend.daemons.log.Process.__init__") as mc_pi:
    #     assert not os.path.exists(self.log_file)
    #     assert not os.path.exists(self.log_dir)
    #     cbl = CoprBackendLog(self.opts, self.queue)
    #
    #     # creates log dir
    #     assert os.path.exists(self.log_dir)
    #
    #     # calls parent init
    #     # TODO: it's tricky to check call to __init__
    #
    # def test_setup_log_handler(self, init_log, mc_logging, capsys):
    #     self.cbl.log = MagicMock()
    #
    #     self.cbl.setup_log_handler()
    #
    #     stdout, stderr = capsys.readouterr()
    #
    #     assert "Running setup handler" in stderr
    #     assert mc_logging.basicConfig.called
    #     assert mc_logging.basicConfig.call_args[1]["filename"] == self.log_file
    #     assert self.cbl.log.called
    #
    # def test_log(self, init_log, capsys):
    #     event = {"who": "main", "when": self.test_time, "what": "foobar"}
    #
    #     self.cbl.setup_log_handler()
    #     self.cbl.log(event)
    #
    #     stdout, stderr = capsys.readouterr()
    #     assert not stdout
    #     assert "Running setup handler" in stderr
    #     assert "foobar" not in stderr
    #
    #     assert os.path.exists(self.log_file)
    #     with open(self.log_file) as handle:
    #         data = handle.read()
    #         assert "Logger initiated" in data
    #         assert "foobar" in data
    #
    # def test_log_verbose(self, init_log, capsys):
    #     self.cbl.opts.verbose = True
    #     event = {"who": "main", "when": self.test_time, "what": "foobar"}
    #
    #     self.cbl.setup_log_handler()
    #     self.cbl.log(event)
    #
    #     stdout, stderr = capsys.readouterr()
    #     assert not stdout
    #     assert "Running setup handler" in stderr
    #     assert "foobar" in stderr
    #
    #     assert os.path.exists(self.log_file)
    #     with open(self.log_file) as handle:
    #         data = handle.read()
    #         assert "Logger initiated" in data
    #         assert "foobar" in data
    #
    # def test_log_error(self, init_log, mc_logging, capsys):
    #     mc_logging.debug.side_effect = IOError("error_message")
    #     event = {"who": "main", "when": self.test_time, "what": "foobar"}
    #
    #     self.cbl.setup_log_handler()
    #     self.cbl.log(event)
    #
    #     stdout, stderr = capsys.readouterr()
    #     assert not stdout
    #     assert "Running setup handler" in stderr
    #     assert "foobar" not in stderr
    #     assert "Could not write to logfile" in stderr
    #
    # def test_run(self, init_log, mc_setproctitle, capsys):
    #     self.cbl.setup_log_handler = MagicMock()
    #
    #     mc_log = MagicMock()
    #     self.cbl.log = mc_log
    #
    #     self.queue.get.side_effect = [
    #         {"who": "main", "when": self.test_time, "what": "foobar"},
    #         {"who": "main", "what": "foobar"},
    #         {"who": "main", "when": self.test_time + 1, "what": "foobar"},
    #     ]
    #
    #     mc_log.side_effect = [
    #         None,
    #         KeyboardInterrupt()
    #     ]
    #     self.cbl.run()
    #
    #     expected = [
    #         mock.call({'what': 'foobar', 'who': 'main', 'when': self.test_time}),
    #         mock.call({'what': 'foobar', 'who': 'main', 'when': self.test_time + 1})
    #     ]
    #     assert expected == mc_log.call_args_list

    # def test_dummy_redis_log_handler(self):
    #     rlh = RedisLogHandler(self.opts)
    #     rlh.run()
    #     # import ipdb; ipdb.set_trace()
    #
    #     x = 2
