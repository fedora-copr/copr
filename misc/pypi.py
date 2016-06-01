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
from copr import CoprClient
import json

URL_PATTERN = 'https://pypi.python.org/pypi/{package}/json'
CONFIG = os.path.join(os.path.expanduser("~"), ".config/copr")

COPR_URL = "https://copr.fedorainfracloud.org/"
USER = "@copr"
COPR = "PyPI2"

cl = CoprClient.create_from_file_config(CONFIG)

parser = argparse.ArgumentParser(prog = "pypi")
parser.add_argument("-s", "--submit-pypi-modules", dest="submit_pypi_modules", action="store_true")
parser.add_argument("-u", "--submit-unbuilt-pypi-modules", dest="submit_unbuilt_pypi_modules", action="store_true")
parser.add_argument("-p", "--parse-succeeded-packages", dest="parse_succeeded_packages", action="store_true")
parser.add_argument("-o", "--parse-succeeded-packages-v1client", dest="parse_succeeded_packages_v1client", action="store_true")
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


def get_all_pypi_modules():
    client = xmlrpclib.ServerProxy('https://pypi.python.org/pypi')
    modules = client.list_packages()
    return modules


def submit_all_pypi_modules():
    for module in get_all_pypi_modules():
        print("Submitting module {0}".format(module))
        submit_build("{}/{}".format(USER, COPR), module, "2")
        time.sleep(4)


def submit_unbuilt_pypi_modules():
    succeeded_modules = get_succeeded_modules()
    for module in get_all_pypi_modules():
        if module in succeeded_modules:
            print("PyPI module '{0}' already built. Skipping.".format(module))
            continue
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
    copr = filter(lambda copr: copr.owner == USER, cl.projects.get_list(name=COPR))[0]
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


def parse_succeeded_packages_v1client():
    for package in get_succeeded_packages():
        print(package.name)


def get_succeeded_packages():
    succeeded_packages = []
    result = cl.get_packages_list(projectname=COPR, ownername=USER, with_latest_succeeded_build=True)
    for package in result.packages_list:
        if package.latest_succeeded_build:
            succeeded_packages.append(package)
    return succeeded_packages


def get_succeeded_modules():
    succeeded_modules = []
    for package in get_succeeded_packages():
        succeeded_modules.append(json.loads(package.source_json)['pypi_package_name'])
    return succeeded_modules


if __name__ == "__main__":
    if args.submit_pypi_modules:
        submit_all_pypi_modules()
    elif args.parse_succeeded_packages:
        parse_succeeded_packages()
    elif args.parse_succeeded_packages_v1client:
        parse_succeeded_packages_v1client()
    elif args.submit_unbuilt_pypi_modules:
        submit_unbuilt_pypi_modules()
    elif args.rebuild_failed_packages:
        rebuild_failed_packages()
    else:
        print("Specify action: See --help")
        parser.print_usage()
