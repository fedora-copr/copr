import sys

import os
import argparse
from collections import defaultdict
import json
from pprint import pprint
from _pytest.capture import capsys
import pytest

import six

if six.PY3:
    from unittest import mock
    from unittest.mock import MagicMock
else:
    import mock
    from mock import MagicMock


sys.path.insert(0, "../run")

from copr_create_repo import main as createrepo_main


@mock.patch("copr_create_repo.createrepo")
class TestArgParser(object):

    def test_arg_parser_good_input(self, mc_createrepo, capsys):
        args = ['-u', 'foo', '-p', 'bar', '-f', 'http://example.com/api/', '/tmp']

        mc_createrepo.return_value = 0, "", ""
        createrepo_main(args)
        assert mc_createrepo.call_args == mock.call(username='foo', projectname='bar',
                                                    front_url='http://example.com/api/', path='/tmp')

    def test_arg_parser_missing_path(self, mc_main, capsys):
        args = ['-u', 'foo', '-p', 'bar', '-f', 'http://example.com/api/']

        with pytest.raises(SystemExit) as err:
            createrepo_main(args)

        assert err.value.code == 1
        stdout, stderr = capsys.readouterr()
        assert "No directory" in stderr

    def test_arg_parser_missing_user(self, mc_main, capsys):
        args = ['-p', 'bar', '-f', 'http://example.com/api/', '/tmp']

        with pytest.raises(SystemExit) as err:
            createrepo_main(args)

        assert err.value.code == 1
        stdout, stderr = capsys.readouterr()
        assert "No user" in stderr

    def test_arg_parser_missing_project(self, mc_main, capsys):
        args = ['-u', 'foo', '-f', 'http://example.com/api/', '/tmp']

        with pytest.raises(SystemExit) as err:
            createrepo_main(args)

        assert err.value.code == 1
        stdout, stderr = capsys.readouterr()
        assert "No project" in stderr

    def test_arg_parser_missing_front(self, mc_main, capsys):
        args = ['-u', 'foo', '-p', 'bar',  '/tmp']

        with pytest.raises(SystemExit) as err:
            createrepo_main(args)

        assert err.value.code == 1
        stdout, stderr = capsys.readouterr()
        assert "No front url" in stderr

