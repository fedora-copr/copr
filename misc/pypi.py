#!/usr/bin/python
import requests
import json
import xmlrpclib
from pip._vendor.packaging.version import parse
import subprocess
import argparse
import time
import os
from copr import create_client2_from_params

URL_PATTERN = 'https://pypi.python.org/pypi/{package}/json'
CONFIG = os.path.join(os.path.expanduser("~"), ".config/copr-dev")

COPR_URL = "http://copr-fe-dev.cloud.fedoraproject.org/"
USER = "msuchy"
COPR = "PyPi-2"


parser = argparse.ArgumentParser(prog = "pypi")
parser.add_argument("-s", "--submit-pypi-modules", dest="submit_pypi_modules", action="store_true")
parser.add_argument("-p", "--parse-succeeded-packages", dest="parse_succeeded_packages", action="store_true")
args = parser.parse_args()


def create_package_name(module_name):
    return "python-{}".format(module_name.replace(".", "-"))


#NOT USED
def get_version(package, url_pattern=URL_PATTERN):
    """Return version of package on pypi.python.org using json."""
    req = requests.get(url_pattern.format(package=package))
    version = parse('0')
    if req.status_code == requests.codes.ok:
        j = json.loads(req.text.encode(req.encoding))
        if 'releases' in j:
            releases = j['releases']
            for release in releases:
                ver = parse(release)
                if not ver.is_prerelease:
                    version = max(version, ver)
    return version


def submit_build(copr_name, module_name, python_version):
    command = ["/usr/bin/copr-cli", "--config", CONFIG,
               "buildpypi", copr_name, "--packagename", module_name,
               "--nowait",
               "--pythonversions", python_version]
    subprocess.call(command)


def submit_all_pypi_modules():
    client = xmlrpclib.ServerProxy('https://pypi.python.org/pypi')
    # get a list of package names
    packages = client.list_packages()
    #print(packages[0:10])
    for module in packages:
        print("Submitting module {0}".format(module))
        submit_build("{}/{}".format(USER, COPR), module, "2")
        time.sleep(4)


def parse_succeeded_packages():
    """
    Print a list of succeeded packages from the USER/COPR repository, one package per line
    If you are looking into this code because you think, that the script froze, be cool. It is just very slow, because
    it iterates 100 results from copr-fe per one result.
    """
    cl = create_client2_from_params(root_url=COPR_URL)
    copr = list(cl.projects.get_list(owner=USER, name=COPR, limit=1))[0]
    packages = {}

    limit = 100
    offset = 0
    while True:
        # @WORKAROUND This code is so ugly because we do not have support for Package resource in api_2 yet.
        # This is why we list all builds and examine their packages.
        builds = cl.builds.get_list(project_id=copr.id, limit=limit, offset=offset)
        if not list(builds):
            break

        for build in filter(lambda x: x.package_name and x.state == "succeeded", builds):
            packages[build.package_name] = build.state
        offset += limit

    for package in packages:
        print(package)


if __name__ == "__main__":
    if args.submit_pypi_modules:
        submit_all_pypi_modules()
    elif args.parse_succeeded_packages:
        parse_succeeded_packages()
    else:
        print("Specify action: See --help")
        parser.print_usage()
