import os
import copy
import tarfile
import tempfile
import shutil
import time
import pytest

from unittest import mock
from unittest.mock import MagicMock

from backend.createrepo import createrepo, createrepo_unsafe, add_appdata, run_cmd_unsafe
from backend.exceptions import CreateRepoError

@mock.patch('backend.createrepo.createrepo_unsafe')
@mock.patch('backend.createrepo.add_appdata')
@mock.patch('backend.helpers.CoprClient')
def test_createrepo_conditional_true(mc_client, mc_add_appdata, mc_create_unsafe):
    mc_client.return_value.get_project_details.return_value = MagicMock(data={"detail": {}})
    mc_create_unsafe.return_value = ""
    mc_add_appdata.return_value = ""

    createrepo(path="/tmp/", front_url="http://example.com/api",
               username="foo", projectname="bar")
    mc_create_unsafe.reset_mock()

    mc_client.return_value.get_project_details.return_value = MagicMock(
        data={"detail": {"auto_createrepo": True}})

    createrepo(path="/tmp/", front_url="http://example.com/api",
               username="foo", projectname="bar")

    mc_create_unsafe.reset_mock()


@mock.patch('backend.createrepo.createrepo_unsafe')
@mock.patch('backend.helpers.CoprClient')
def test_createrepo_conditional_false(mc_client, mc_create_unsafe):
    mc_client.return_value.get_project_details.return_value = MagicMock(data={"detail": {"auto_createrepo": False}})

    base_url = "http://example.com/repo/"
    createrepo(path="/tmp/", front_url="http://example.com/api",
               username="foo", projectname="bar", base_url=base_url)

    assert mc_create_unsafe.call_args == mock.call('/tmp/', dest_dir='devel', base_url=base_url)


@pytest.yield_fixture
def mc_popen():
    with mock.patch('backend.createrepo.Popen') as handle:
        yield handle


@pytest.yield_fixture
def mc_run_cmd_unsafe():
    with mock.patch('backend.createrepo.run_cmd_unsafe') as handle:
        yield handle


class TestCreaterepo(object):
    def setup_method(self, method):
        self.tmp_dir_name = self.make_temp_dir()
        self.test_time = time.time()
        self.base_url = "http://example.com/repo/"

        self.username = "foo"
        self.projectname = "bar"

    # def unpack_resource(self, resource_name):
    #     if self.tmp_dir_name is None:
    #         self.make_temp_dir()
    #
    #     src_path = os.path.join(os.path.dirname(__file__),
    #                             "_resources", resource_name)
    #
    #     with tarfile.open(src_path, "r:gz") as tfile:
    #         tfile.extractall(os.path.join(self.tmp_dir_name, "old_dir"))

    def teardown_method(self, method):
        self.rm_tmp_dir()

    def rm_tmp_dir(self):
        if self.tmp_dir_name:
            shutil.rmtree(self.tmp_dir_name)
            self.tmp_dir_name = None

    def make_temp_dir(self):
        root_tmp_dir = tempfile.gettempdir()
        subdir = "test_createrepo_{}".format(time.time())
        self.tmp_dir_name = os.path.join(root_tmp_dir, subdir)
        os.mkdir(self.tmp_dir_name)
        return self.tmp_dir_name

    #def test_add_appdata(self, mc_run_cmd_unsafe):
    #    todo: implement, need to test behaviour with/withou produced appstream files
    #    for lock in [None, MagicMock()]:
    #        add_appdata(self.tmp_dir_name, self.username, self.projectname, lock=lock)
    #        print mc_run_cmd_unsafe.call_args_list
    #        mc_run_cmd_unsafe.reset()

    def test_run_cmd_unsafe_ok(self, mc_popen):
        cmd = "foo --bar"
        mc_popen.return_value.communicate.return_value = ("stdout", "stderr")
        mc_popen.return_value.returncode = 0

        assert run_cmd_unsafe(cmd, self.tmp_dir_name, lock_path="/tmp") == "stdout"
        mc_popen.reset()

    def test_run_cmd_unsafe_err_popen(self, mc_popen):
        cmd = "foo --bar"
        mc_popen.side_effect = IOError()

        with pytest.raises(CreateRepoError) as err:
            run_cmd_unsafe(cmd, self.tmp_dir_name, lock_path="/tmp") == "stdout"

        assert err.value.cmd == cmd
        assert mc_popen.call_args[0][0] == ["foo", "--bar"]
        mc_popen.reset()

    def test_run_cmd_unsafe_err_return_code(self, mc_popen):
        cmd = "foo --bar"
        mc_popen.return_value.communicate.return_value = ("stdout", "stderr")
        mc_popen.return_value.returncode = 1


        with pytest.raises(CreateRepoError) as err:
            run_cmd_unsafe(cmd, self.tmp_dir_name, lock_path="/tmp") == "stdout"

        assert err.value.cmd == cmd
        assert err.value.stdout == "stdout"
        assert err.value.stderr == "stderr"
        assert err.value.exit_code == 1
        assert mc_popen.call_args[0][0] == ["foo", "--bar"]
        mc_popen.reset()

    def test_run_cmd_unsafe_err_communicate(self, mc_popen):
        cmd = "foo --bar"
        mc_handle = MagicMock()
        mc_popen.return_value = MagicMock()
        mc_handle.returncode = 0
        mc_handle.side_effect = RuntimeError()

        with pytest.raises(CreateRepoError) as err:
            run_cmd_unsafe(cmd, self.tmp_dir_name, lock_path="/tmp") == "stdout"

        assert err.value.cmd == cmd
        assert mc_popen.call_args[0][0] == ["foo", "--bar"]
        mc_popen.reset()

    def test_createrepo_generated_commands_existing_repodata(self, mc_run_cmd_unsafe):
        path_epel_5 = os.path.join(self.tmp_dir_name, "epel-5")
        expected_epel_5 = ('/usr/bin/createrepo_c --database --ignore-lock --local-sqlite --cachedir /tmp/ --workers 8 '
                           '--update -s sha --checksum md5 ' + path_epel_5)
        path_fedora = os.path.join(self.tmp_dir_name, "fedora-21")
        expected_fedora = ('/usr/bin/createrepo_c --database --ignore-lock --local-sqlite --cachedir /tmp/ --workers 8 '
                           '--update ' + path_fedora)
        for path, expected in [(path_epel_5, expected_epel_5), (path_fedora, expected_fedora)]:
            os.makedirs(path)

            repo_path = os.path.join(path, "repodata")
            os.makedirs(repo_path)
            with open(os.path.join(repo_path, "repomd.xml"), "w") as handle:
                handle.write("1")

            createrepo_unsafe(path)
            assert mc_run_cmd_unsafe.call_args[0][0] == expected

    def test_createrepo_generated_commands_comps_xml(self, mc_run_cmd_unsafe):
        path_epel_5 = os.path.join(self.tmp_dir_name, "epel-5")
        path_fedora = os.path.join(self.tmp_dir_name, "fedora-21")
        for path in [path_epel_5, path_fedora]:
            for add_comps in [True, False]:
                os.makedirs(path)

                comps_path = os.path.join(path, "comps.xml")
                if add_comps:
                    with open(comps_path, "w") as handle:
                        handle.write("1")

                repo_path = os.path.join(path, "repodata")
                os.makedirs(repo_path)
                with open(os.path.join(repo_path, "repomd.xml"), "w") as handle:
                    handle.write("1")

                createrepo_unsafe(path)
                if add_comps:
                    assert "--groupfile" in mc_run_cmd_unsafe.call_args[0][0]
                else:
                    assert "--groupfile" not in mc_run_cmd_unsafe.call_args[0][0]
                mc_run_cmd_unsafe.mock_reset()
                shutil.rmtree(path, ignore_errors=True)

    def test_createrepo_devel_generated_commands_existing_repodata(self, mc_run_cmd_unsafe):
        path_epel_5 = os.path.join(self.tmp_dir_name, "epel-5")
        expected_epel_5 = ("/usr/bin/createrepo_c --database --ignore-lock --local-sqlite --cachedir /tmp/ --workers 8 "
                           "-s sha --checksum md5 "
                           "--outputdir " + os.path.join(path_epel_5, "devel") + " "
                           "--baseurl " + self.base_url + " " + path_epel_5)
        path_fedora = os.path.join(self.tmp_dir_name, "fedora-21")
        expected_fedora = ("/usr/bin/createrepo_c --database --ignore-lock --local-sqlite --cachedir /tmp/ --workers 8 "
                           "--outputdir " + os.path.join(path_fedora, "devel") + " "
                           "--baseurl " + self.base_url + " " + path_fedora)
        for path, expected in [(path_epel_5, expected_epel_5), (path_fedora, expected_fedora)]:
            os.makedirs(path)

            repo_path = os.path.join(path, "devel", "repodata")
            os.makedirs(repo_path)
            with open(os.path.join(repo_path, "repomd.xml"), "w") as handle:
                handle.write("1")

            createrepo_unsafe(path, base_url=self.base_url, dest_dir="devel")
            assert mc_run_cmd_unsafe.call_args[0][0] == expected

    def test_createrepo_devel_generated_commands(self, mc_run_cmd_unsafe):
        path_epel_5 = os.path.join(self.tmp_dir_name, "epel-5")
        expected_epel_5 = ("/usr/bin/createrepo_c --database --ignore-lock --local-sqlite --cachedir /tmp/ --workers 8 "
                           "-s sha --checksum md5 "
                           "--outputdir " + os.path.join(path_epel_5, "devel") + " "
                           "--baseurl " + self.base_url + " " + path_epel_5)
        path_fedora = os.path.join(self.tmp_dir_name, "fedora-21")
        expected_fedora = ("/usr/bin/createrepo_c --database --ignore-lock --local-sqlite --cachedir /tmp/ --workers 8 "
                           "--outputdir " + os.path.join(path_fedora, "devel") + " "
                           "--baseurl " + self.base_url + " " + path_fedora)
        for path, expected in [(path_epel_5, expected_epel_5), (path_fedora, expected_fedora)]:
            os.makedirs(path)

            createrepo_unsafe(path, base_url=self.base_url, dest_dir="devel")
            assert os.path.exists(os.path.join(path, "devel"))
            assert mc_run_cmd_unsafe.call_args[0][0] == expected
            # assert mc_popen.call_args == mock.call(expected, stderr=-1, stdout=-1)

    def test_createrepo_devel_creates_folder(self, mc_run_cmd_unsafe):
        path_epel_5 = os.path.join(self.tmp_dir_name, "epel-5")
        path_fedora = os.path.join(self.tmp_dir_name, "fedora-21")

        for path in [path_epel_5, path_fedora]:
            os.makedirs(path)

            createrepo_unsafe(path, base_url=self.base_url, dest_dir="devel")
            assert os.path.exists(os.path.join(path, "devel"))
