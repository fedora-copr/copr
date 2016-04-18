#!/usr/bin/python
import requests
import json
import xmlrpclib
from pip._vendor.packaging.version import parse
import subprocess
import time

URL_PATTERN = 'https://pypi.python.org/pypi/{package}/json'
CONFIG = "/home/msuchy/.config/copr-dev"

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

client = xmlrpclib.ServerProxy('https://pypi.python.org/pypi')
# get a list of package names
packages = client.list_packages()
#print(packages[0:10])
for module in packages:
    print("Submitting module {0}".format(module))
    submit_build("msuchy/PyPi-2", module, "2")
    time.sleep(4)
