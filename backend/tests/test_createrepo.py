import os
import copy
import tarfile
import tempfile
import shutil
import time

import six

if six.PY3:
    from unittest import mock
    from unittest.mock import MagicMock
else:
    import mock
    from mock import MagicMock


from backend.createrepo import createrepo, createrepo_unsafe, add_appdata


@mock.patch('backend.createrepo.createrepo_unsafe')
@mock.patch('backend.createrepo.add_appdata')
@mock.patch('backend.helpers.CoprClient')
def test_createrepo_conditional_true(mc_client, mc_add_appdata, mc_create_unsafe):
    mc_client.return_value.get_project_details.return_value = MagicMock(data={"detail": {}})
    mc_create_unsafe.return_value = ""
    mc_add_appdata.return_value = ""

    createrepo(path="/tmp/", front_url="http://example.com/api",
               username="foo", projectname="bar", lock=None)
    mc_create_unsafe.reset_mock()

    mc_client.return_value.get_project_details.return_value = MagicMock(
        data={"detail": {"auto_createrepo": True}})

    createrepo(path="/tmp/", front_url="http://example.com/api",
               username="foo", projectname="bar", lock=None)

    mc_create_unsafe.reset_mock()


@mock.patch('backend.createrepo.createrepo_unsafe')
@mock.patch('backend.helpers.CoprClient')
def test_createrepo_conditional_false(mc_client, mc_create_unsafe):
    mc_client.return_value.get_project_details.return_value = MagicMock(data={"detail": {"auto_createrepo": False}})

    base_url = "http://example.com/repo/"
    createrepo(path="/tmp/", front_url="http://example.com/api",
               username="foo", projectname="bar", base_url=base_url, lock=None)

    assert mc_create_unsafe.call_args == mock.call('/tmp/', None, dest_dir='devel', base_url=base_url)


@mock.patch('backend.createrepo.Popen')
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

    def test_run_cmd_unsafe(self, mc_popen):
        # todo: implement & simplify createrepo_unsafe tests
        pass

    def disabled_test_add_appdata(self, mc_popen):
        # todo: re-enable
        mc_popen.return_value.returncode = 0
        mc_popen.return_value.communicate.return_value = "stdout", ""
        add_appdata(self.tmp_dir_name, self.username, self.projectname)
        expected = [
            mock.call([
                '/usr/bin/appstream-builder',
                '--api-version=0.8',
                '--verbose',
                '--add-cache-id',
                # '--min-icon-size=48',
                # '--enable-hidpi',
                # '--include-failed',
                '--max-threads=4',
                '--temp-dir={}/tmp'.format(self.tmp_dir_name),
                '--cache-dir={}/cache'.format(self.tmp_dir_name),
                '--packages-dir={}'.format(self.tmp_dir_name),
                '--output-dir={}/appdata'.format(self.tmp_dir_name),
                '--basename=appstream',
                '--origin={}/{}'.format(self.username, self.projectname)], stderr=-1, stdout=-1),
            mock.call([
                '/usr/bin/modifyrepo_c',
                '--no-compress',
                '{}/appdata/appstream.xml.gz'.format(self.tmp_dir_name),
                '{}/repodata'.format(self.tmp_dir_name)], stderr=-1, stdout=-1)]
        assert expected == mc_popen.call_args_list

    def test_createrepo_unsafe_lock_usage(self, mc_popen):
        mocked_lock = MagicMock()
        self.shared_state = dict(in_lock=False, lock_status=None)

        def enter_lock(*args, **kwargs):
            self.shared_state["in_lock"] = True

        def exit_lock(*args, **kwargs):
            self.shared_state["in_lock"] = False

        def popen_side_effect(*args, **kwargs):
            self.shared_state["lock_status"] = copy.copy(self.shared_state["in_lock"])
            return mock.DEFAULT

        mocked_lock.__enter__.side_effect = enter_lock
        mocked_lock.__exit__.side_effect = exit_lock

        mc_popen.side_effect = popen_side_effect
        mc_popen.return_value.communicate.return_value = ("", "")
        mc_popen.return_value.returncode = 0

        createrepo_unsafe(self.tmp_dir_name, lock=mocked_lock)
        assert self.shared_state["lock_status"]

        self.shared_state["lock_status"] = None
        createrepo_unsafe(self.tmp_dir_name, lock=None)
        assert not self.shared_state["lock_status"]

    def disabled_test_createrepo_generated_commands_existing_repodata(self, mc_popen):
        # todo: re-enable
        mc_popen.return_value.communicate.return_value = ("", "")
        mc_popen.return_value.returncode = 0
        path_epel_5 = os.path.join(self.tmp_dir_name, "epel-5")
        expected_epel_5 = ['/usr/bin/createrepo_c', '--database',
                           '--ignore-lock', '--update', '-s', 'sha', '--checksum', 'md5', path_epel_5]
        path_fedora = os.path.join(self.tmp_dir_name, "fedora-21")
        expected_fedora = ['/usr/bin/createrepo_c', '--database',
                           '--ignore-lock', '--update', path_fedora]
        for path, expected in [(path_epel_5, expected_epel_5), (path_fedora, expected_fedora)]:
            os.makedirs(path)

            repo_path = os.path.join(path, "repodata")
            os.makedirs(repo_path)
            with open(os.path.join(repo_path, "repomd.xml"), "w") as handle:
                handle.write("1")

            createrepo_unsafe(path, None)
            assert mc_popen.call_args == mock.call(expected, stderr=-1, stdout=-1)

    def disabled_test_createrepo_devel_generated_commands_existing_repodata(self, mc_popen):
        # todo: re-enable
        mc_popen.return_value.communicate.return_value = ("", "")
        mc_popen.return_value.returncode = 0
        path_epel_5 = os.path.join(self.tmp_dir_name, "epel-5")
        expected_epel_5 = ['/usr/bin/createrepo_c', '--database', '--ignore-lock',
                           '-s', 'sha', '--checksum', 'md5',
                           '--outputdir', os.path.join(path_epel_5, "devel"),
                           '--baseurl', self.base_url, path_epel_5]
        path_fedora = os.path.join(self.tmp_dir_name, "fedora-21")
        expected_fedora = ['/usr/bin/createrepo_c', '--database', '--ignore-lock',
                           '--outputdir', os.path.join(path_fedora, "devel"),
                           '--baseurl', self.base_url, path_fedora]
        for path, expected in [(path_epel_5, expected_epel_5), (path_fedora, expected_fedora)]:
            os.makedirs(path)

            repo_path = os.path.join(path, "devel", "repodata")
            os.makedirs(repo_path)
            with open(os.path.join(repo_path, "repomd.xml"), "w") as handle:
                handle.write("1")

            createrepo_unsafe(path, lock=None, base_url=self.base_url, dest_dir="devel")
            assert mc_popen.call_args == mock.call(expected, stderr=-1, stdout=-1)

    def disabled_test_createrepo_devel_generated_commands(self, mc_popen):
        # todo: re-enable

        mc_popen.return_value.communicate.return_value = ("", "")
        mc_popen.return_value.returncode = 0
        path_epel_5 = os.path.join(self.tmp_dir_name, "epel-5")
        expected_epel_5 = ['/usr/bin/createrepo_c', '--database', '--ignore-lock',
                           '-s', 'sha', '--checksum', 'md5',
                           '--outputdir', os.path.join(path_epel_5, "devel"),
                           '--baseurl', self.base_url, path_epel_5]
        path_fedora = os.path.join(self.tmp_dir_name, "fedora-21")
        expected_fedora = ['/usr/bin/createrepo_c', '--database', '--ignore-lock',
                           '--outputdir', os.path.join(path_fedora, "devel"),
                           '--baseurl', self.base_url, path_fedora]
        for path, expected in [(path_epel_5, expected_epel_5), (path_fedora, expected_fedora)]:
            os.makedirs(path)

            createrepo_unsafe(path, lock=None, base_url=self.base_url, dest_dir="devel")
            assert os.path.exists(os.path.join(path, "devel"))
            assert mc_popen.call_args == mock.call(expected, stderr=-1, stdout=-1)
    #
    # def test_createrepo_devel_creates_folder(self, mc_popen):
    #
    #     mc_popen.return_value.communicate.return_value = ("", "")
    #     path_epel_5 = os.path.join(self.tmp_dir_name, "epel-5")
    #     path_fedora = os.path.join(self.tmp_dir_name, "fedora-21")
    #
    #     for path in [path_epel_5, path_fedora]:
    #         os.makedirs(path)
    #
    #         createrepo_unsafe(path, lock=None, base_url=self.base_url, dest_dir="devel")
    #         assert os.path.exists(os.path.join(path, "devel"))
