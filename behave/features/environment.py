""" Configuration for Copr BDD tests. """

import configparser
import os
import time
from urllib.parse import urlparse

from copr_behave_lib import run_check, CoprCli

def _get_mock_target_for_host():
    cmd = ["rpm", "--eval",
           "%{?fedora:fedora}%{?rhel:epel}-%{?fedora}%{?rhel}-%_arch"]
    (out, _) = run_check(cmd)
    return out.strip()


def before_all(context):
    """ Execute once per behave run """
    context.started = time.time()

    context.system_chroot = _get_mock_target_for_host()

    context.frontend_url = os.environ.get(
        "FRONTEND_URL",
        "https://copr.stg.fedoraproject.org")
    context.backend_url = os.environ.get(
        "BACKEND_URL",
        "https://copr-be-dev.cloud.fedoraproject.org")
    context.copr_cli_config = os.environ.get(
        "COPR_CLI_CONFIG",
        "~/.config/copr")

    context.cli = CoprCli(context)
    context.builds = []
    context.last_project_name = None
    context.last_package_name = None

    # check that API points to valid frontend
    parsed_fronted = urlparse(context.frontend_url)
    context.copr_cli_config = os.path.expanduser(context.copr_cli_config)
    if not os.path.exists(context.copr_cli_config):
        raise Exception("Missing {}".format(context.copr_cli_config))
    parser = configparser.ConfigParser()
    parser.read(context.copr_cli_config)
    api_frontend_url = parser['copr-cli']['copr_url']
    parsed_api = urlparse(api_frontend_url)
    if parsed_api.hostname != parsed_fronted.hostname:
        raise Exception("Url {} from ~/.config/copr isn't {}".format(
            parsed_api.hostname, parsed_fronted.hostname))

def after_scenario(_context, _scenario):
    """ hook called after each scenario, hit a debugger here """
