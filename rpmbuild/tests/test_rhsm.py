import os
import sys
import io
import importlib
from unittest import mock, skipIf

try:
    import subscription_manager
except ImportError:
    subscription_manager = None


def load_module(mod, filename, caller_filename=None):
    if caller_filename:
        filename = os.path.realpath(os.path.join(caller_filename, "..",
                                                 filename))

    # With the help of:
    # https://stackoverflow.com/questions/2601047/import-a-python-module-without-the-py-extension
    spec = importlib.util.spec_from_loader(
        mod,
        importlib.machinery.SourceFileLoader(mod, filename),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules[mod] = module
    return module


@skipIf(subscription_manager is None, "subscription-manager not installed")
def test_rhsm_subscribe_script():
    with mock.patch("os.getuid", return_value=0):
        script = load_module("script",
                             "../bin/copr-builder-rhsm-subscribe",
                             __file__)
        sys.argv = ["foo", "--org-id", "1", "--system-name", "system"]

        with mock.patch("sys.stdin", io.StringIO("foo")):
            with mock.patch("script.rhsm"):
                script._main()  # pylint: disable=protected-access
                assert sys.argv == ['subscription-manager', 'register',
                                    '--force', '--org', '1', '--name', 'system',
                                    '--activationkey', 'foo']
