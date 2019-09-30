import six

if six.PY3:
    from unittest import mock
    from unittest.mock import MagicMock
else:
    import mock
    from mock import MagicMock

import pytest

config = {
    "username": None,
    "copr_url": "http://copr/",
    "login": "",
    "token": "",
}

@pytest.yield_fixture
def f_test_config():
    with mock.patch('copr_cli.main.config_from_file',
                    return_value=config) as test_config:
        yield test_config
