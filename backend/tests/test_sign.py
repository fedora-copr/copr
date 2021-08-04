import os
import tempfile
import shutil
import time

from munch import Munch
import pytest

from copr_backend.exceptions import CoprSignError, CoprSignNoKeyError, CoprKeygenRequestError

from unittest import mock
from unittest.mock import MagicMock

from copr_backend.sign import get_pubkey, _sign_one, sign_rpms_in_dir, create_user_keys


STDOUT = "stdout"
STDERR = "stderr"


class TestSign(object):

    def setup_method(self, method):
        self.username = "foo"
        self.projectname = "bar"

        self.usermail = "foo#bar@copr.fedorahosted.org"
        self.test_time = time.time()
        self.tmp_dir_path = None

        self.opts = Munch(keygen_host="example.com")

    def teardown_method(self, method):
        if self.tmp_dir_path:
            shutil.rmtree(self.tmp_dir_path)

    @pytest.fixture
    def tmp_dir(self):
        subdir = "test_createrepo_{}".format(time.time())
        self.tmp_dir_path = os.path.join(tempfile.gettempdir(), subdir)
        os.mkdir(self.tmp_dir_path)

    @pytest.fixture
    def tmp_files(self):
        # ! require tmp_dir created before
        self.file_names = ["foo.rpm", "bar.rpm", "bad", "morebadrpm"]
        for name in self.file_names:
            path = os.path.join(self.tmp_dir_path, name)
            with open(path, "w") as handle:
                handle.write("1")

    @mock.patch("copr_backend.sign.Popen")
    def test_get_pubkey(self, mc_popen):
        mc_handle = MagicMock()
        mc_handle.communicate.return_value = (STDOUT, STDERR)
        mc_handle.returncode = 0
        mc_popen.return_value = mc_handle

        result = get_pubkey(self.username, self.projectname, MagicMock())
        assert result == STDOUT
        assert mc_popen.call_args[0][0] == ['/bin/sign', '-u', self.usermail, '-p']


    @mock.patch("copr_backend.sign.Popen")
    def test_get_pubkey_error(self, mc_popen):
        mc_popen.side_effect = IOError(STDERR)

        with pytest.raises(CoprSignError):
            get_pubkey(self.username, self.projectname, MagicMock())


    @mock.patch("copr_backend.sign.Popen")
    def test_get_pubkey_unknown_key(self, mc_popen):
        mc_handle = MagicMock()
        mc_handle.communicate.return_value = (STDOUT, "unknown key: foobar")
        mc_handle.returncode = 1
        mc_popen.return_value = mc_handle

        with pytest.raises(CoprSignNoKeyError) as err:
            get_pubkey(self.username, self.projectname, MagicMock())

        assert "There are no gpg keys for user foo in keyring" in str(err)

    @mock.patch("copr_backend.sign.Popen")
    def test_get_pubkey_unknown_error(self, mc_popen):
        mc_handle = MagicMock()
        mc_handle.communicate.return_value = (STDOUT, STDERR)
        mc_handle.returncode = 1
        mc_popen.return_value = mc_handle

        with pytest.raises(CoprSignError) as err:
            get_pubkey(self.username, self.projectname, MagicMock())

        assert "Failed to get user pubkey" in str(err)

    @mock.patch("copr_backend.sign.Popen")
    def test_get_pubkey_outfile(self, mc_popen, tmp_dir):
        mc_handle = MagicMock()
        mc_handle.communicate.return_value = (STDOUT, STDERR)
        mc_handle.returncode = 0
        mc_popen.return_value = mc_handle

        outfile_path = os.path.join(self.tmp_dir_path, "out.pub")
        assert not os.path.exists(outfile_path)
        result = get_pubkey(self.username, self.projectname, MagicMock(),
                            outfile_path)
        assert result == STDOUT
        assert os.path.exists(outfile_path)
        with open(outfile_path) as handle:
            content = handle.read()
            assert STDOUT == content

    @mock.patch("copr_backend.sign.Popen")
    def test_sign_one(self, mc_popen):
        mc_handle = MagicMock()
        mc_handle.communicate.return_value = (STDOUT, STDERR)
        mc_handle.returncode = 0
        mc_popen.return_value = mc_handle

        fake_path = "/tmp/pkg.rpm"
        result = _sign_one(fake_path, self.usermail, MagicMock())
        assert STDOUT, STDERR == result

        expected_cmd = ['/bin/sign', '-u', self.usermail, '-r', fake_path]
        assert mc_popen.call_args[0][0] == expected_cmd

    @mock.patch("copr_backend.sign.Popen")
    def test_sign_one_popen_error(self, mc_popen):
        mc_popen.side_effect = IOError()

        fake_path = "/tmp/pkg.rpm"
        with pytest.raises(CoprSignError):
            _sign_one(fake_path, self.usermail, MagicMock())

    @mock.patch("copr_backend.sign.Popen")
    def test_sign_one_cmd_erro(self, mc_popen):
        mc_handle = MagicMock()
        mc_handle.communicate.return_value = (STDOUT, STDERR)
        mc_handle.returncode = 1
        mc_popen.return_value = mc_handle

        fake_path = "/tmp/pkg.rpm"
        with pytest.raises(CoprSignError):
            _sign_one(fake_path, self.usermail, MagicMock())

    @mock.patch("copr_backend.sign.request")
    def test_create_user_keys(self, mc_request):
        mc_request.return_value.status_code = 200
        create_user_keys(self.username, self.projectname, self.opts)

        assert mc_request.called
        expected_call = mock.call(
            url="http://example.com/gen_key",
            data='{"name_real": "foo_bar", "name_email": "foo_bar@copr.fedorahosted.org"}',
            method="post"
        )
        assert mc_request.call_args == expected_call

    @mock.patch("copr_backend.sign.request")
    def test_create_user_keys_error_1(self, mc_request):
        mc_request.side_effect = IOError()
        with pytest.raises(CoprKeygenRequestError) as err:
            create_user_keys(self.username, self.projectname, self.opts)

        assert "Failed to create key-pair" in str(err)


    @mock.patch("copr_backend.sign.request")
    def test_create_user_keys(self, mc_request):
        for code in [400, 401, 404, 500, 599]:
            mc_request.return_value.status_code = code
            mc_request.return_value.content = "error: {}".format(code)

            with pytest.raises(CoprKeygenRequestError) as err:
                create_user_keys(self.username, self.projectname, self.opts)
            assert "Failed to create key-pair for user: foo, project:bar" in str(err)

    @mock.patch("copr_backend.sign._sign_one")
    @mock.patch("copr_backend.sign.create_user_keys")
    @mock.patch("copr_backend.sign.get_pubkey")
    def test_sign_rpms_id_dir_nothing(self, mc_gp, mc_cuk, mc_so,
                                      tmp_dir):
        # empty target dir doesn't produce error
        sign_rpms_in_dir(self.username, self.projectname,
                         self.tmp_dir_path, self.opts, log=MagicMock())

        assert not mc_gp.called
        assert not mc_cuk.called
        assert not mc_so.called

    @mock.patch("copr_backend.sign._sign_one")
    @mock.patch("copr_backend.sign.create_user_keys")
    @mock.patch("copr_backend.sign.get_pubkey")
    def test_sign_rpms_id_dir_ok(self, mc_gp, mc_cuk, mc_so,
                                      tmp_dir, tmp_files):

        sign_rpms_in_dir(self.username, self.projectname,
                         self.tmp_dir_path, self.opts, log=MagicMock())

        assert mc_gp.called
        assert not mc_cuk.called
        assert mc_so.called

        pathes = [call[0][0] for call in mc_so.call_args_list]
        count = 0
        for name in self.file_names:
            if name.endswith(".rpm"):
                count += 1
                assert os.path.join(self.tmp_dir_path, name) in pathes
        assert len(pathes) == count

    @mock.patch("copr_backend.sign._sign_one")
    @mock.patch("copr_backend.sign.create_user_keys")
    @mock.patch("copr_backend.sign.get_pubkey")
    def test_sign_rpms_id_dir_error_on_pubkey(
            self, mc_gp, mc_cuk, mc_so, tmp_dir, tmp_files):

        mc_gp.side_effect = CoprSignError("foobar")
        with pytest.raises(CoprSignError):
            sign_rpms_in_dir(self.username, self.projectname,
                             self.tmp_dir_path, self.opts, log=MagicMock())

        assert mc_gp.called
        assert not mc_cuk.called
        assert not mc_so.called

    @mock.patch("copr_backend.sign._sign_one")
    @mock.patch("copr_backend.sign.create_user_keys")
    @mock.patch("copr_backend.sign.get_pubkey")
    def test_sign_rpms_id_dir_no_pub_key(
            self, mc_gp, mc_cuk, mc_so, tmp_dir, tmp_files):

        mc_gp.side_effect = CoprSignNoKeyError("foobar")

        sign_rpms_in_dir(self.username, self.projectname,
                         self.tmp_dir_path, self.opts, log=MagicMock())

        assert mc_gp.called
        assert mc_cuk.called
        assert mc_so.called

    @mock.patch("copr_backend.sign._sign_one")
    @mock.patch("copr_backend.sign.create_user_keys")
    @mock.patch("copr_backend.sign.get_pubkey")
    def test_sign_rpms_id_dir_sign_error_one(
            self, mc_gp, mc_cuk, mc_so, tmp_dir, tmp_files):

        mc_so.side_effect = [
            None, CoprSignError("foobar"), None
        ]
        with pytest.raises(CoprSignError):
            sign_rpms_in_dir(self.username, self.projectname,
                             self.tmp_dir_path, self.opts, log=MagicMock())

        assert mc_gp.called
        assert not mc_cuk.called

        assert mc_so.called

    @mock.patch("copr_backend.sign._sign_one")
    @mock.patch("copr_backend.sign.create_user_keys")
    @mock.patch("copr_backend.sign.get_pubkey")
    def test_sign_rpms_id_dir_sign_error_all(
            self, mc_gp, mc_cuk, mc_so, tmp_dir, tmp_files):

        mc_so.side_effect = CoprSignError("foobar")
        with pytest.raises(CoprSignError):
            sign_rpms_in_dir(self.username, self.projectname,
                             self.tmp_dir_path, self.opts, log=MagicMock())

        assert mc_gp.called
        assert not mc_cuk.called

        assert mc_so.called
