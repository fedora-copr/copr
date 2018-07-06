import os

from requests.models import Response

from copr import CoprClient

try:
     from unittest import mock
except ImportError:
     # Python 2 version depends on mock
     import mock

path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)
resource_location = os.path.join(dir_path, "resources")
config_location = os.path.join(resource_location, "copr_cli.conf")


def test_client_from_dict():
    cl = CoprClient(
        login="api-login",
        username="user_name",
        token="api-token",
        copr_url="http://copr-fe-dev.cloud.fedoraproject.org"
    )

    assert isinstance(cl, CoprClient)
    assert cl.login == "api-login"
    assert cl.token == "api-token"
    assert cl.username == "user_name"


def test_client_from_config():
    cl = CoprClient.create_from_file_config(config_location)
    assert isinstance(cl, CoprClient)
    assert cl.login == "api-login"
    assert cl.token == "api-token"
    assert cl.username == "user_name"


def test_list_projects():
    CoprClient.create_from_file_config(config_location)


# TODO: package https://github.com/dropbox/responses and use it
def make_mock_response(filename, status_code=None):
    response = Response()
    response.status_code = status_code or 200
    response.encoding = "utf-8"
    with open(os.path.join(resource_location, filename)) as text:
        response._content = text.read().encode()
    return response


@mock.patch('requests.request')
def test_projects_list(mock_request):
    mock_client = CoprClient.create_from_file_config(config_location)
    mock_request.return_value = make_mock_response("projects_list.200.json")

    test_resp = mock_client.get_projects_list()
    assert len(test_resp.projects_list) == 1
    test_project = test_resp.projects_list[0]
    assert test_project.projectname == "perl516-el7"
    assert test_project.description == "Test description"


@mock.patch('requests.request')
def test_get_build_status(mock_request):
    mock_client = CoprClient.create_from_file_config(config_location)

    mock_request.return_value = make_mock_response("build_details.200.json")

    test_resp = mock_client.get_build_details(27382)

    assert test_resp.status == "succeeded"
    assert test_resp.project == "atomic-next"
    assert test_resp.built_pkgs == [u'golang-github-stretchr-objx-devel 0']
    assert test_resp.submitted_on == 1408031345
