from unittest import TestCase
import tempfile
import shutil
import os

import six

if six.PY3:
    from unittest import mock
    from unittest.mock import patch
else:
    import mock
    from mock import patch

import pytest

from copr_keygen import app
from copr_keygen.exceptions import GpgErrorException, KeygenServiceBaseException
from copr_keygen.logic import ensure_passphrase_exist

import copr_keygen.logic as logic


TMP_DIR = tempfile.gettempdir()

TEST_EMAIL = "foobar@example.com"
TEST_NAME = "foobar"
TEST_KEYLENGTH = 2048


class TestEnsurePassphrase(TestCase):
    def __init__(self, *args, **kwargs):
        super(TestEnsurePassphrase, self).__init__(*args, **kwargs)
        self.path = None
        from copr_keygen import app as mock_app

        self.mock_app = mock_app

    @property
    def target(self):
        return os.path.join(self.path, TEST_EMAIL)

    def setUp(self):
        self.path = tempfile.mkdtemp()
        self.mock_app.config["PHRASES_DIR"] = self.path

    def tearDown(self):
        shutil.rmtree(self.path)

    def test_file_creation(self):
        ensure_passphrase_exist(self.mock_app, TEST_EMAIL)

        assert os.path.exists(self.target)
        assert os.path.getsize(self.target) > 0

    def test_add_content_to_empty_file(self):
        open(self.target, "w").close()
        assert os.path.getsize(self.target) == 0
        ensure_passphrase_exist(self.mock_app, TEST_EMAIL)
        assert os.path.getsize(self.target) > 0


def test_ensure_passphrase_exist():
    path = os.path.join(TMP_DIR, "TEST_GNUPG_PASSPHRASES")
    os.mkdir(path)
    try:
        from copr_keygen import app as mock_app

        mock_app.config["PHRASES_DIR"] = path
        ensure_passphrase_exist(mock_app, TEST_EMAIL)

        target = os.path.join(path, TEST_EMAIL)
        assert os.path.exists(target)
        assert os.path.getsize(target) > 0

        # now we placing empty file
        os.remove(target)
        open(target, "w").close()
        assert os.path.getsize(target) == 0
        ensure_passphrase_exist(mock_app, TEST_EMAIL)
        assert os.path.getsize(target) > 0

    except Exception as e:
        shutil.rmtree(path, ignore_errors=True)
        raise e

    shutil.rmtree(path, ignore_errors=True)


class MockPopenHandle(object):
    def __init__(self, returncode=None, stdout=None, stderr=None):
        self.returncode = returncode or 0
        self.stdout = stdout or "mock stdout"
        self.stderr = stderr or "mock stderr"

    def communicate(self):
        return self.stdout.encode(), self.stderr.encode()


@mock.patch("copr_keygen.logic.ensure_passphrase_exist")
@mock.patch("copr_keygen.logic.Popen")
class TestUserExists(TestCase):
    def test_exists(self, popen, ensure_passphrase):
        popen.return_value = MockPopenHandle(0)
        ensure_passphrase.return_value = True
        assert logic.user_exists(app, TEST_EMAIL)

    def test_not_exists(self, popen, ensure_passphrase):
        popen.return_value = MockPopenHandle(1, stderr="error reading key")
        ensure_passphrase.return_value = True
        assert not logic.user_exists(app, TEST_EMAIL)

    def test_gpg_unknown_err(self, popen, ensure_passphrase):
        popen.return_value = MockPopenHandle(1)
        with pytest.raises(GpgErrorException):
            logic.user_exists(app, TEST_EMAIL)

    def test_popen_unknown_err(self, popen, ensure_passphrase):
        popen.side_effect = OSError()
        with pytest.raises(GpgErrorException):
            logic.user_exists(app, TEST_EMAIL)


@mock.patch("copr_keygen.logic.user_exists")
@mock.patch("copr_keygen.logic.Popen")
class TestGenKey(TestCase):
    def test_simple_create(self, popen, user_exists):
        """
        Check correct key generation.
        """

        with mock.patch("tempfile.NamedTemporaryFile") as tmpfile:
            def check_gpg_genkey_file_exists(*args, **kwargs):
                assert tmpfile.called
                return MockPopenHandle(0)

            popen.side_effect = check_gpg_genkey_file_exists

            res = logic.create_new_key(app, TEST_NAME, TEST_EMAIL, TEST_KEYLENGTH)
            assert res is None

    def test_strange_situation_create(self, popen, user_exists):
        """
        After key generation `user_exists` invoked again, and if it doesn't
        see key it should raise an error
        """

        user_exists.return_value = False
        popen.return_value = MockPopenHandle(0)

        with pytest.raises(GpgErrorException):
            logic.create_new_key(app, TEST_NAME, TEST_EMAIL, TEST_KEYLENGTH)

    def test_error_popen(self, popen, user_exists):
        user_exists.return_value = False
        popen.side_effect = OSError()
        with pytest.raises(GpgErrorException):
            logic.create_new_key(app, TEST_NAME, TEST_EMAIL, TEST_KEYLENGTH)

    def test_error_gpg(self, popen, user_exists):
        user_exists.return_value = False
        err_msg = "Error message 123"
        popen.return_value = MockPopenHandle(1, stderr=err_msg)
        with pytest.raises(GpgErrorException) as e:
            logic.create_new_key(app, TEST_NAME, TEST_EMAIL, TEST_KEYLENGTH)
            assert e.message == err_msg

    def test_tmpfiles_errors(self, popen, user_exists):
        user_exists.return_value = False

        with mock.patch("tempfile.NamedTemporaryFile") as tmpfile:
            tmpfile.side_effect = OSError()
            with pytest.raises(KeygenServiceBaseException) as e:
                logic.create_new_key(app, TEST_NAME, TEST_EMAIL, TEST_KEYLENGTH)

            assert not popen.called

        with mock.patch("tempfile.NamedTemporaryFile") as tmpfile:
            tmpfile.return_value.write.side_effect = OSError()
            with pytest.raises(KeygenServiceBaseException) as e:
                logic.create_new_key(app, TEST_NAME, TEST_EMAIL, TEST_KEYLENGTH)

            assert not popen.called
