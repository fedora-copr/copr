import unittest
import tempfile
import shutil
import os
from unittest import mock

import pytest

from copr_rpmbuild.helpers import string2list, locate_srpm, download_file

class TestHelpers(unittest.TestCase):
    def test_string2list(self):
        self.assertEqual(string2list('foo bar baz'), ['foo', 'bar', 'baz'])
        self.assertEqual(string2list('foo,bar,baz'), ['foo', 'bar', 'baz'])
        self.assertEqual(string2list('  foo bar\nbaz,'), ['foo', 'bar', 'baz'])
        self.assertEqual(string2list(',,foo, \nbar\tbaz,,'), ['foo', 'bar', 'baz'])
        self.assertEqual(string2list(',,foo\tbar\tbaz'), ['foo', 'bar', 'baz'])

    def test_locate_srpm(self):
        tmpdir = tempfile.mkdtemp(prefix="copr-rpmbuild-test-")
        srpm_path = os.path.join(tmpdir, "dummy.src.rpm")
        open(srpm_path, "w").close()
        self.assertEqual(srpm_path, locate_srpm(tmpdir))
        shutil.rmtree(tmpdir)


class TestDownloadFile:
    @staticmethod
    def _fake_response(chunks):
        response = mock.MagicMock()
        response.iter_content.return_value = iter(chunks)
        # a real requests.Response.__exit__ never suppresses exceptions;
        # MagicMock's default (truthy) return value would incorrectly
        # swallow the OSError we expect to propagate in some tests
        response.__exit__.return_value = False
        return response

    @mock.patch("copr_rpmbuild.helpers.SafeRequest")
    def test_success(self, mc_safe_request):
        response = self._fake_response([b"hello", b" world"])
        mc_safe_request.return_value.send.return_value = response

        with tempfile.TemporaryDirectory(prefix="copr-test-download") as destdir:
            filepath = download_file(
                "http://example.com/hello-1.0-1.fc40.x86_64.rpm", destdir)

            assert filepath == os.path.join(
                destdir, "hello-1.0-1.fc40.x86_64.rpm")
            with open(filepath, "rb") as f:
                assert f.read() == b"hello world"

        response.__exit__.assert_called_once()

    @mock.patch("copr_rpmbuild.helpers.SafeRequest")
    def test_response_is_closed_on_write_failure(self, mc_safe_request):
        response = self._fake_response([b"hello"])
        mc_safe_request.return_value.send.return_value = response

        # destdir doesn't exist -> open() raises OSError while streaming
        with pytest.raises(RuntimeError):
            download_file(
                "http://example.com/hello-1.0-1.fc40.x86_64.rpm",
                "/no/such/directory")

        # even though writing failed, the response must still be closed
        # rather than leaking the underlying connection
        response.__exit__.assert_called_once()

    @mock.patch("copr_rpmbuild.helpers.SafeRequest")
    def test_encoded_traversal_stays_in_destdir(self, mc_safe_request):
        # a URL-encoded "../../etc/pwn" must not escape destdir: the
        # decoded path is reduced to its basename ("pwn") before any file
        # is opened, same as a plain (non-encoded) traversal attempt would
        # be handled by os.path.basename()
        response = self._fake_response([b"pwned"])
        mc_safe_request.return_value.send.return_value = response

        with tempfile.TemporaryDirectory(prefix="copr-test-download") as destdir:
            filepath = download_file(
                "http://example.com/..%2f..%2fetc%2fpwn", destdir)

            assert filepath == os.path.join(destdir, "pwn")
            assert os.listdir(destdir) == ["pwn"]

    @mock.patch("copr_rpmbuild.helpers.SafeRequest")
    def test_rejects_empty_filename(self, mc_safe_request):
        response = self._fake_response([b"data"])
        mc_safe_request.return_value.send.return_value = response

        with tempfile.TemporaryDirectory(prefix="copr-test-download") as destdir:
            with pytest.raises(RuntimeError):
                download_file("http://example.com/", destdir)

            assert os.listdir(destdir) == []
