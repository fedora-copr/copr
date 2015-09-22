from copy import deepcopy
import six

if six.PY3:
    from unittest import mock
else:
    import mock

from coprs import app
from coprs.helpers import parse_package_name, generate_repo_url, \
    fix_protocol_for_frontend, fix_protocol_for_backend

from tests.coprs_test_case import CoprsTestCase


class TestHelpers(CoprsTestCase):

    def test_guess_package_name(self):
        EXP = {
            'wat-1.2.rpm': 'wat',
            'will-crash-0.5-2.fc20.src.rpm': 'will-crash',
            'will-crash-0.5-2.fc20.src': 'will-crash',
            'will-crash-0.5-2.fc20': 'will-crash',
            'will-crash-0.5-2': 'will-crash',
            'will-crash-0.5-2.rpm': 'will-crash',
            'will-crash-0.5-2.src.rpm': 'will-crash',
            'will-crash': 'will-crash',
            'pkgname7.src.rpm': 'pkgname7',
            'copr-frontend-1.14-1.git.65.9ba5393.fc20.noarch': 'copr-frontend',
            'noversion.fc20.src.rpm': 'noversion',
            'nothing': 'nothing',
            'ruby193': 'ruby193',
            'xorg-x11-fonts-ISO8859-1-75dpi-7.1-2.1.el5.noarch.rpm': 'xorg-x11-fonts-ISO8859-1-75dpi',
        }

        for pkg, expected in EXP.items():
            assert parse_package_name(pkg) == expected

    def test_generate_repo_url(self):
        test_sets = []
        http_url = "http://example.com/repo"
        https_url = "https://example.com/repo"

        mock_chroot = mock.MagicMock()
        mock_chroot.os_release = "fedora"
        mock_chroot.os_version = "20"

        test_sets.extend([
            dict(args=(mock_chroot, http_url),
                 expected="http://example.com/fedora-$releasever-$basearch/"),
            dict(args=(mock_chroot, https_url),
                 expected="https://example.com/fedora-$releasever-$basearch/")])

        m2 = deepcopy(mock_chroot)
        m2.os_version = "rawhide"

        test_sets.extend([
            dict(args=(m2, http_url),
                 expected="http://example.com/fedora-rawhide-$basearch/"),
            dict(args=(m2, https_url),
                 expected="https://example.com/fedora-rawhide-$basearch/")])

        m3 = deepcopy(mock_chroot)
        m3.os_release = "rhel7"
        m3.os_version = "7.1"

        test_sets.extend([
            dict(args=(m3, http_url),
                 expected="http://example.com/rhel7-7.1-$basearch/"),
            dict(args=(m3, https_url),
                 expected="https://example.com/rhel7-7.1-$basearch/")])

        app.config["USE_HTTPS_FOR_RESULTS"] = True
        for test_set in test_sets:
            result = generate_repo_url(*test_set["args"])
            assert result == test_set["expected"]

    def test_fix_protocol_for_backend(self):
        http_url = "http://example.com/repo"
        https_url = "https://example.com/repo"

        orig = app.config["ENFORCE_PROTOCOL_FOR_BACKEND_URL"]
        try:
            app.config["ENFORCE_PROTOCOL_FOR_BACKEND_URL"] = "https"
            assert fix_protocol_for_backend(https_url) == https_url
            assert fix_protocol_for_backend(http_url) == https_url

            app.config["ENFORCE_PROTOCOL_FOR_BACKEND_URL"] = "http"
            assert fix_protocol_for_backend(https_url) == http_url
            assert fix_protocol_for_backend(http_url) == http_url

            app.config["ENFORCE_PROTOCOL_FOR_BACKEND_URL"] = None
            assert fix_protocol_for_backend(https_url) == https_url
            assert fix_protocol_for_backend(http_url) == http_url

        except Exception as e:
            app.config["ENFORCE_PROTOCOL_FOR_BACKEND_URL"] = orig
            raise e
        app.config["ENFORCE_PROTOCOL_FOR_BACKEND_URL"] = orig

    def test_fix_protocol_for_frontend(self):
        http_url = "http://example.com/repo"
        https_url = "https://example.com/repo"

        orig = app.config["ENFORCE_PROTOCOL_FOR_FRONTEND_URL"]
        try:
            app.config["ENFORCE_PROTOCOL_FOR_FRONTEND_URL"] = "https"
            assert fix_protocol_for_frontend(https_url) == https_url
            assert fix_protocol_for_frontend(http_url) == https_url

            app.config["ENFORCE_PROTOCOL_FOR_FRONTEND_URL"] = "http"
            assert fix_protocol_for_frontend(https_url) == http_url
            assert fix_protocol_for_frontend(http_url) == http_url

            app.config["ENFORCE_PROTOCOL_FOR_FRONTEND_URL"] = None
            assert fix_protocol_for_frontend(https_url) == https_url
            assert fix_protocol_for_frontend(http_url) == http_url

        except Exception as e:
            app.config["ENFORCE_PROTOCOL_FOR_FRONTEND_URL"] = orig
            raise e
        app.config["ENFORCE_PROTOCOL_FOR_BACKEND_URL"] = orig
