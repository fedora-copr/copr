# pylint: disable=ungrouped-imports
try:
    from unittest import mock
    from unittest.mock import MagicMock
    from pytest import fixture
except ImportError:
    import mock
    from mock import MagicMock
    from pytest import yield_fixture as fixture


config = {
    "username": "jdoe",
    "copr_url": "http://copr/",
    "login": "xyz",
    "token": "abc",
}


@fixture
def f_test_config():
    with mock.patch('copr_cli.main.config_from_file',
                    return_value=config) as test_config:
        yield test_config
