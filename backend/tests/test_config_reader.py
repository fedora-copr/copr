""" tests for BackendConfigReader class """

import shutil
import tempfile

import pytest

from copr_backend.exceptions import CoprBackendError
from copr_backend.helpers import BackendConfigReader

class TestBackendConfigReader:
    minimal_config_snippet = (
        "[backend]\n"
        "destdir=/tmp\n"
    )
    workdir = None

    def setup_method(self, method):
        _side_effects = [method]
        self.workdir = tempfile.mkdtemp(prefix="copr-test-config-")

    def teardown_method(self, method):
        _side_effects = [method]
        shutil.rmtree(self.workdir)

    def get_config_file(self, file_contents):
        """ return filename which has the configuration """
        tfile = tempfile.NamedTemporaryFile(mode="w", dir=self.workdir, delete=False)
        tfile.file.write(file_contents)
        tfile.close()
        return tfile.name

    def get_minimal_config_file(self):
        """ return filename with any (minimal) configuration """
        return self.get_config_file(self.minimal_config_snippet)

    def test_minimal_file_and_defaults(self):
        opts = BackendConfigReader(self.get_minimal_config_file()).read()
        assert opts.destdir == "/tmp"
        assert opts.builds_limits == {'arch': {}, 'tag': {}, 'owner': 20, 'sandbox': 10}

    def test_correct_build_limits(self):
        opts = BackendConfigReader(
            self.get_config_file(
                self.minimal_config_snippet + (
                    "builds_max_workers= 666\n"
                    "builds_max_workers_arch= x86_64 =5, aarch64= 11\n"
                    "builds_max_workers_tag = Power9=9\n"
                    "builds_max_workers_owner = 5\n"
                    "builds_max_workers_sandbox = 3\n"
                ))).read()
        assert opts.builds_limits == {
            'arch': {
                'x86_64': 5,
                'aarch64': 11,
            },
            'tag': {
                'Power9': 9,
            },
            'owner': 5,
            'sandbox': 3
        }

    @pytest.mark.parametrize("broken_config", [
        "builds_max_workers=asdfa\n",
        "actions_max_workers=asdfa\n",
    ])
    def test_invalid_limits(self, broken_config):
        config = self.minimal_config_snippet + broken_config
        with pytest.raises(ValueError):
            BackendConfigReader(self.get_config_file(config)).read()

    @pytest.mark.parametrize("broken_config", [
        "builds_max_workers_arch=abc\n",
        "builds_max_workers_arch=abc=asdf\n",
        "builds_max_workers_arch=abc=10=\n",
        "builds_max_workers_arch=abc=1,\n",
        "builds_max_workers_tag=abc=1,\n",
    ])
    def test_invalid_build_limits(self, broken_config):
        config = self.minimal_config_snippet + broken_config
        with pytest.raises(CoprBackendError):
            BackendConfigReader(self.get_config_file(config)).read()
