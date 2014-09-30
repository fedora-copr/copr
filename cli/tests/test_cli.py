from collections import defaultdict
import json
from pprint import pprint
from _pytest.capture import capsys
import pytest

import six
import copr
from copr.client.parsers import ProjectListParser, CommonMsgErrorOutParser
from copr.client.responses import CoprResponse
from copr.client.exceptions import CoprConfigException, CoprNoConfException
from copr.client import CoprClient
import copr_cli
from copr_cli.main import no_config_warning


if six.PY3:
    from unittest import mock
    from unittest.mock import MagicMock
else:
    import mock
    from mock import MagicMock


import logging

logging.basicConfig(
level=logging.INFO,
format= '[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
datefmt='%H:%M:%S'
)

log = logging.getLogger()
log.info("Logger initiated")


from copr_cli import main


@mock.patch('copr_cli.main.CoprClient')
def test_cancel_build_no_config(mock_cc, capsys):
    #mock_from_config.return_value = CoprClient(dict(no_config=True))
    mock_cc.create_from_file_config.side_effect = CoprNoConfException()

    with pytest.raises(SystemExit) as err:
        main.main(argv=["cancel", "123400"])

    assert err.value.code == 6
    out, err = capsys.readouterr()
    assert ("Error: Operation requires api authentication\n"
            "File `~/.config/copr` is missing or incorrect\n") in out

    expected_warning = no_config_warning
    assert expected_warning in out



@mock.patch('copr_cli.main.CoprClient')
def test_cancel_build_response(mock_cc, capsys):
    response_status = "foobar"

    mock_client = MagicMock(no_config=False,)
    mock_client.cancel_build.return_value = MagicMock(status=response_status)
    mock_cc.create_from_file_config.return_value = mock_client

    main.main(argv=["cancel", "123"])
    out, err = capsys.readouterr()
    assert "{}\n".format(response_status) in out



@mock.patch('copr_cli.main.CoprClient')
def test_list_project(mock_cc,  capsys):
    response_data = {"output": "ok",
    "repos": [
      {u'additional_repos': u'http://copr-be.cloud.fedoraproject.org/results/rhscl/httpd24/epel-6-$basearch/ http://copr-be.cloud.fedoraproject.org/results/msuchy/scl-utils/epel-6-$basearch/ http://people.redhat.com/~msuchy/rhscl-1.1-rhel-6-candidate-perl516/',
   u'description': u'A recent stable release of Perl with a number of additional utilities, scripts, and database connectors for MySQL and PostgreSQL. This version provides a large number of new features and enhancements, including new debugging options, improved Unicode support, and better performance.',
   u'instructions': u'',
   u'name': u'perl516',
   u'yum_repos': {u'epel-6-x86_64': u'http://copr-be.cloud.fedoraproject.org/results/rhscl/perl516/epel-6-x86_64/'}},
  {u'additional_repos': u'http://copr-be.cloud.fedoraproject.org/results/msuchy/scl-utils/epel-6-$basearch/ http://copr-be.cloud.fedoraproject.org/results/rhscl/httpd24/epel-6-$basearch/ http://copr-be.cloud.fedoraproject.org/results/rhscl/v8314/epel-6-$basearch/',
   u'description': u'A recent stable release of Ruby with Rails 3.2.8 and a large collection of Ruby gems. This Software Collection gives developers on Red Hat Enterprise Linux 6 access to Ruby 1.9, which provides a number of new features and enhancements, including improved Unicode support, enhanced threading, and faster load times.',
   u'instructions': u'',
   u'name': u'ruby193',
   u'yum_repos': {u'epel-6-x86_64': u'http://copr-be.cloud.fedoraproject.org/results/rhscl/ruby193/epel-6-x86_64/'}}]}

    expected_output = """Name: perl516
  Description: A recent stable release of Perl with a number of additional utilities, scripts, and database connectors for MySQL and PostgreSQL. This version provides a large number of new features and enhancements, including new debugging options, improved Unicode support, and better performance.
  Yum repo(s):
    epel-6-x86_64: http://copr-be.cloud.fedoraproject.org/results/rhscl/perl516/epel-6-x86_64/
  Additional repo: http://copr-be.cloud.fedoraproject.org/results/rhscl/httpd24/epel-6-$basearch/ http://copr-be.cloud.fedoraproject.org/results/msuchy/scl-utils/epel-6-$basearch/ http://people.redhat.com/~msuchy/rhscl-1.1-rhel-6-candidate-perl516/

Name: ruby193
  Description: A recent stable release of Ruby with Rails 3.2.8 and a large collection of Ruby gems. This Software Collection gives developers on Red Hat Enterprise Linux 6 access to Ruby 1.9, which provides a number of new features and enhancements, including improved Unicode support, enhanced threading, and faster load times.
  Yum repo(s):
    epel-6-x86_64: http://copr-be.cloud.fedoraproject.org/results/rhscl/ruby193/epel-6-x86_64/
  Additional repo: http://copr-be.cloud.fedoraproject.org/results/msuchy/scl-utils/epel-6-$basearch/ http://copr-be.cloud.fedoraproject.org/results/rhscl/httpd24/epel-6-$basearch/ http://copr-be.cloud.fedoraproject.org/results/rhscl/v8314/epel-6-$basearch/
"""
    e2 = """Name: perl516
  Description: A recent stable release of Perl with a number of additional utilities, scripts, and database connectors for MySQL and PostgreSQL. This version provides a large number of new features and enhancements, including new debugging options, improved Unicode support, and better performance.
  Yum repo(s):
    epel-6-x86_64: http://copr-be.cloud.fedoraproject.org/results/rhscl/perl516/epel-6-x86_64/
  Additional repo: http://copr-be.cloud.fedoraproject.org/results/rhscl/httpd24/epel-6-$basearch/ http://copr-be.cloud.fedoraproject.org/results/msuchy/scl-utils/epel-6-$basearch/ http://people.redhat.com/~msuchy/rhscl-1.1-rhel-6-candidate-perl516/

Name: ruby193
  Description: A recent stable release of Ruby with Rails 3.2.8 and a large collection of Ruby gems. This Software Collection gives developers on Red Hat Enterprise Linux 6 access to Ruby 1.9, which provides a number of new features and enhancements, including improved Unicode support, enhanced threading, and faster load times.
"""

    # no config
    mock_cc.create_from_file_config.side_effect = CoprNoConfException()
    mocked_client = MagicMock(CoprClient(dict(no_config=True)))

    control_response = CoprResponse(client=None, method="", data=response_data,
                                    parsers=[ProjectListParser, CommonMsgErrorOutParser])
    mocked_client.get_projects_list.return_value = control_response
    mock_cc.return_value = mocked_client

    main.main(argv=["list", "rhscl"])

    out, err = capsys.readouterr()
    assert expected_output in out


    expected_warning = no_config_warning
    assert expected_warning in out






